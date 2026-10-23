"""Import source catalog metadata through native Studio APIs, without changing dates."""
import hashlib
import json
from html import escape
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from opaque_keys.edx.keys import CourseKey


# Only public catalog fields belong in a learner-visible overview.
SECTIONS = (
    ('full_description', 'About this course'),
    ('target_audience', 'Who this course is for'),
    ('prerequisite_course_keys', 'Required prerequisites'),
    ('recommended_prerequisites', 'Recommended prerequisites'),
    ('learning_outcomes', 'Learning outcomes'),
    ('syllabus', 'Syllabus'),
    ('assessment_summary', 'Assessment'),
    ('completion_requirements', 'Completion requirements'),
    ('references', 'References'),
    ('level', 'Level'), ('delivery_format', 'Delivery format'),
    ('language', 'Language'), ('duration_minutes', 'Planned duration (minutes)'),
    ('price', 'Listed price'), ('currency', 'Currency'),
    ('credential', 'Credential'), ('takeaway', 'Takeaway'),
    ('catalog_categories', 'Catalog categories'),
    ('content_version', 'Content version'),
)


def render_value(value):
    if isinstance(value, list):
        return '<ul>' + ''.join('<li>' + escape(str(item)) + '</li>' for item in value) + '</ul>'
    return ''.join('<p>' + escape(part).replace('\n', '<br>') + '</p>' for part in str(value).split('\n\n'))


def metadata_values(record):
    short = record.get('short_description')
    if not isinstance(short, str) or not short.strip():
        raise ValueError('A nonempty short_description is required.')
    if not isinstance(record.get('full_description'), str) or not record['full_description'].strip():
        raise ValueError('A nonempty full_description is required.')
    sections = []
    for field, label in SECTIONS:
        value = record.get(field)
        if value is not None and value != '' and value != []:
            sections.append('<section><h2>' + label + '</h2>' + render_value(value) + '</section>')
    pacing = record.get('pacing')
    if pacing not in ('self_paced', 'instructor_paced'):
        raise ValueError('pacing must be self_paced or instructor_paced.')
    language = record.get('language')
    if not isinstance(language, str) or not language.strip():
        raise ValueError('A language is required.')
    return {'short_description': short, 'overview': '\n'.join(sections),
            'language': language, 'self_paced': pacing == 'self_paced'}


class Command(BaseCommand):
    help = 'Populate existing Studio course metadata; default is validation only.'

    def add_arguments(self, parser):
        parser.add_argument('catalog_file', type=Path)
        parser.add_argument('--course-key', required=True)
        parser.add_argument('--author', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--backup-file', type=Path)

    def handle(self, *args, **options):
        from openedx.core.djangoapps.models.course_details import CourseDetails
        from xmodule.modulestore.django import modulestore
        from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole

        try:
            source = options['catalog_file'].read_bytes()
            payload = json.loads(source)
            key = CourseKey.from_string(options['course_key'])
            matches = [r for r in payload['microcourses'] if r.get('course_key') == str(key)]
            if len(matches) != 1:
                raise ValueError('Expected exactly one selected source course.')
            record = matches[0]
            values = metadata_values(record)
            user_model = get_user_model()
            user = user_model.objects.get(**{user_model.USERNAME_FIELD: options['author']})
            if not user.is_active or not (user.is_superuser or CourseInstructorRole(key).has_user(user) or CourseStaffRole(key).has_user(user)):
                raise ValueError('An active course author is required.')
            store = modulestore()
            course = store.get_course(key)
            if course is None:
                raise ValueError('Create the selected course before importing metadata.')
            if course.catalog_visibility != 'none' or course.invitation_only is not True:
                raise ValueError('This import requires a hidden, invitation-only course.')
            if not course.can_toggle_course_pacing and course.self_paced != values['self_paced']:
                raise ValueError('Native Studio does not allow this pacing change.')
            details = CourseDetails.fetch(key)
            sidecar = payload.get('sidecar', payload.get('sidecars', {})).get(str(key), {})
            if 'sidecar' in payload and 'sidecars' in payload and payload['sidecar'] != payload['sidecars']:
                raise ValueError('Conflicting sidecar aliases.')
        except (ValueError, KeyError, TypeError, OSError, ObjectDoesNotExist) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f'Course: {key}; overview characters: {len(values["overview"])}')
        if not options['apply']:
            self.stdout.write('VALIDATED: metadata only; no writes. No lessons, awards or approval changes.')
            return
        backup = options.get('backup_file')
        if backup is None:
            raise CommandError('--backup-file is required with --apply.')
        snapshot = {'course_key': str(key), 'source_sha256': hashlib.sha256(source).hexdigest(),
                    'source_record': record, 'sidecar': sidecar,
                    'before': {name: getattr(details, name, None) for name in ('short_description', 'overview')},
                    'native_before': {name: getattr(course, name) for name in ('language', 'self_paced', 'catalog_visibility', 'invitation_only')}}
        # Exclusive creation prevents overwriting an earlier recovery snapshot.
        with backup.open('x', encoding='utf-8') as stream:
            import os
            os.chmod(backup, 0o600)
            json.dump(snapshot, stream, indent=2)
        with store.bulk_operations(key):
            course.language = values['language']
            course.self_paced = values['self_paced']
            store.update_item(course, user.id)
            for name in ('short_description', 'overview'):
                CourseDetails.update_about_item(course, name, values[name], user.id, store=store)
        actual = CourseDetails.fetch(key)
        for name in ('short_description', 'overview', 'language', 'self_paced'):
            if getattr(actual, name) != values[name]:
                raise CommandError('Read-back verification failed: ' + name + '. Backup: ' + str(backup))
        current = store.get_course(key)
        if current.catalog_visibility != 'none' or current.invitation_only is not True:
            raise CommandError('Visibility verification failed.')
        self.stdout.write('PASS: descriptions, source overview, language and pacing imported and verified.')
        self.stdout.write('Source record and private sidecar preserved in backup: ' + str(backup))
        self.stdout.write('No lessons created; dates and credit plans were not edited.')
