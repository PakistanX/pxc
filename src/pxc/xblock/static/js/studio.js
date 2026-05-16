// Studio init for the PXC xblock author view. Open edX wires this up via
// frag.initialize_js("PxcStudioXBlock") and calls it once the fragment is in
// the DOM with the XBlock runtime + the root element.
//
// Uses jQuery's $.ajax so Open edX's global $.ajaxSetup attaches X-CSRFToken
// from the csrftoken cookie automatically — native fetch() drops the header
// and the save_settings handler then 403s.
function PxcStudioXBlock(runtime, element) {
  if (!customElements.get("pxc-activity")) {
    customElements.define("pxc-activity", XBlockPXC);
  }

  var handlerUrl = runtime.handlerUrl(element, "save_settings");

  $(element).find(".save-button").on("click", function (e) {
    e.preventDefault();
    var slug = $(element).find("#pxc-activity-select").val();
    var displayName = $(element).find("#pxc-display-name").val();
    runtime.notify("save", { state: "start" });
    $.ajax({
      url: handlerUrl,
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ activity_slug: slug, display_name: displayName }),
      success: function () {
        runtime.notify("save", { state: "end" });
      },
      error: function (xhr) {
        runtime.notify("error", {
          title: "PXC save failed",
          message: xhr.responseText || xhr.statusText,
        });
      },
    });
  });

  $(element).find(".cancel-button").on("click", function (e) {
    e.preventDefault();
    runtime.notify("cancel", {});
  });
}
