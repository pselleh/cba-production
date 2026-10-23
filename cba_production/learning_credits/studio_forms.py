"""Course authoring forms: credits are calculated, never entered manually."""

from decimal import Decimal

from django import forms
from django.forms import formset_factory

from .models import CourseCreditPlan


class OutcomeLinesField(forms.CharField):
    def prepare_value(self, value):
        return "\n".join(value) if isinstance(value, list) else value

    def to_python(self, value):
        return [line.strip() for line in super().to_python(value).splitlines() if line.strip()]


class CreditPlanForm(forms.ModelForm):
    learning_outcomes = OutcomeLinesField(
        label="Learning outcomes", required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one intended learning outcome per line.",
    )
    required_block_keys = forms.MultipleChoiceField(
        label="Required activities", required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = CourseCreditPlan
        fields = (
            "version", "instruction_minutes", "assignments_minutes",
            "assessments_minutes", "discussions_minutes", "other_minutes",
            "instructional_design_reference", "learning_outcomes", "required_block_keys",
        )
        labels = {
            "instruction_minutes": "Instruction minutes",
            "assignments_minutes": "Assignment minutes",
            "assessments_minutes": "Quiz and examination minutes",
            "discussions_minutes": "Discussion minutes",
            "other_minutes": "Other activity minutes",
            "instructional_design_reference": "Instructional design reference",
        }
        help_texts = {
            name: "Leave blank if unknown. Enter 0 when this activity is not required."
            for name in (
                "instruction_minutes", "assignments_minutes", "assessments_minutes",
                "discussions_minutes", "other_minutes",
            )
        }

    def __init__(self, *args, activities, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["required_block_keys"].choices = [
            (activity["key"], activity["label"]) for activity in activities
        ]


class ActivityRequirementForm(forms.Form):
    activity = forms.ChoiceField(label="Activity")
    category = forms.ChoiceField(choices=(
        ("", "Choose a category"),
        ("assignments", "Assignment"), ("assessments", "Assessment"),
        ("discussions", "Discussion"),
    ))
    minimum_percent = forms.DecimalField(
        label="Minimum passing percentage", min_value=0, max_value=100,
        decimal_places=2, max_digits=5, required=False,
    )
    minimum_posts = forms.IntegerField(label="Original posts", min_value=0, required=False)
    minimum_responses = forms.IntegerField(label="Responses to other learners", min_value=0, required=False)

    def __init__(self, *args, activities, **kwargs):
        super().__init__(*args, **kwargs)
        self.activities = {item["key"]: item for item in activities}
        self.fields["activity"].choices = [("", "Choose an activity")] + [
            (item["key"], item["label"]) for item in activities
            if item["type"] in {"openassessment", "discussion"}
        ]

    def clean(self):
        values = super().clean()
        item = self.activities.get(values.get("activity"))
        if item is None:
            return values
        if item["type"] == "openassessment":
            if values.get("category") not in {"assignments", "assessments"}:
                self.add_error("category", "Select Assignment or Assessment.")
            if values.get("minimum_percent") is None:
                self.add_error("minimum_percent", "Enter the approved passing percentage.")
            if values.get("minimum_posts") is not None or values.get("minimum_responses") is not None:
                raise forms.ValidationError("Discussion counts do not apply to an assignment.")
        elif item["type"] == "discussion":
            if values.get("category") != "discussions":
                self.add_error("category", "Select Discussion.")
            counts = (values.get("minimum_posts"), values.get("minimum_responses"))
            if any(value is None for value in counts) or not sum(value or 0 for value in counts):
                raise forms.ValidationError("Enter both counts, including explicit zeros; require at least one contribution.")
            if values.get("minimum_percent") is not None:
                self.add_error("minimum_percent", "A participation requirement does not have a passing score.")
        return values

    def rule(self):
        values = self.cleaned_data
        result = {"block_key": values["activity"], "category": values["category"]}
        if self.activities[values["activity"]]["type"] == "openassessment":
            result.update(kind="ora_score", minimum_fraction=str(values["minimum_percent"] / Decimal(100)))
        else:
            result.update(
                kind="discussion_participation", minimum_posts=values["minimum_posts"],
                minimum_responses=values["minimum_responses"],
            )
        return result


RequirementFormSet = formset_factory(
    ActivityRequirementForm, extra=1, can_delete=True,
    max_num=200, validate_max=True, absolute_max=400,
)


def requirement_initial(rules):
    result = []
    for rule in rules:
        row = {"activity": rule["block_key"], "category": rule["category"]}
        if rule["kind"] == "ora_score":
            row["minimum_percent"] = Decimal(rule["minimum_fraction"]) * 100
        else:
            row.update(minimum_posts=rule["minimum_posts"], minimum_responses=rule["minimum_responses"])
        result.append(row)
    return result
