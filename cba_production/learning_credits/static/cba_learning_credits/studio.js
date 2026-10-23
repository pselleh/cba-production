"use strict";
document.getElementById("add-requirement")?.addEventListener("click", () => {
  const total = document.getElementById("id_requirements-TOTAL_FORMS");
  const count = Number(total.value);
  if (count >= 200) return;
  const html = document.getElementById("empty-requirement").innerHTML.replaceAll("__prefix__", String(count));
  document.getElementById("requirement-rows").insertAdjacentHTML("beforeend", html);
  total.value = String(count + 1);
});
