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
    var hasScore = $(element).find("#pxc-has-score").is(":checked");
    var weight = $(element).find("#pxc-weight").val();
    runtime.notify("save", { state: "start" });
    $.ajax({
      url: handlerUrl,
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({
        activity_slug: slug,
        display_name: displayName,
        has_score: hasScore,
        weight: weight,
      }),
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

  var resetUrl = runtime.handlerUrl(element, "reset_learner");
  var $resetButton = $(element).find("#pxc-reset-button");
  var $resetStatus = $(element).find("#pxc-reset-status");

  $resetButton.on("click", function (e) {
    e.preventDefault();
    if ($resetButton.hasClass("is-busy")) {
      return;
    }
    var email = $(element).find("#pxc-reset-email").val().trim();
    if (!email) {
      $resetStatus.text("Enter a student email first.").attr("class", "tip setting-help pxc-reset-status pxc-status-error");
      return;
    }
    $resetButton.addClass("is-busy is-disabled");
    $resetStatus.text("Resetting…").attr("class", "tip setting-help pxc-reset-status");
    $.ajax({
      url: resetUrl,
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ email: email }),
      success: function (resp) {
        $resetStatus
          .text(
            "Reset " + resp.username + ": " + resp.fields_deleted + " field(s), " +
            resp.log_entries_deleted + " log entr(y/ies) cleared."
          )
          .attr("class", "tip setting-help pxc-reset-status pxc-status-success");
      },
      error: function (xhr) {
        $resetStatus
          .text("Reset failed: " + (xhr.responseText || xhr.statusText))
          .attr("class", "tip setting-help pxc-reset-status pxc-status-error");
      },
      complete: function () {
        $resetButton.removeClass("is-busy is-disabled");
      },
    });
  });

  // Upload widget is always rendered (see studio_view.html); enforcement of
  // who's actually allowed to upload happens server-side in the handler.
  var $widget = $(element).find("#pxc-upload-widget");
  if ($widget.length === 0) {
    return;
  }

  var uploadUrl = runtime.handlerUrl(element, "upload_activity");
  var $fileInput = $(element).find("#pxc-upload-bundle");
  var $dropzone = $(element).find("#pxc-upload-dropzone");
  var $filename = $(element).find("#pxc-upload-filename");
  var $button = $(element).find("#pxc-upload-button");
  var $status = $(element).find("#pxc-upload-status");

  function setStatus(text, kind) {
    $status
      .text(text)
      .removeClass("pxc-status-error pxc-status-success")
      .addClass(kind ? "pxc-status-" + kind : "");
  }

  function updateFilenameDisplay() {
    var file = $fileInput[0].files[0];
    $filename.text(file ? file.name : "");
  }

  $fileInput.on("change", updateFilenameDisplay);

  // Drag-and-drop onto the dropzone label (native <input type=file> drop
  // handling is unreliable across browsers, so we intercept it ourselves).
  $dropzone.on("dragover dragenter", function (e) {
    e.preventDefault();
    $dropzone.addClass("pxc-drag-over");
  });
  $dropzone.on("dragleave dragend drop", function () {
    $dropzone.removeClass("pxc-drag-over");
  });
  $dropzone.on("drop", function (e) {
    e.preventDefault();
    var files = e.originalEvent.dataTransfer && e.originalEvent.dataTransfer.files;
    if (files && files.length > 0) {
      $fileInput[0].files = files;
      updateFilenameDisplay();
    }
  });

  $button.on("click", function (e) {
    e.preventDefault();
    if ($button.hasClass("is-busy")) {
      return;
    }
    var file = $fileInput[0].files[0];
    if (!file) {
      setStatus("Choose a .zip file first.", "error");
      return;
    }
    var formData = new FormData();
    formData.append("bundle", file);
    $button.addClass("is-busy is-disabled");
    setStatus("Uploading and building…");
    $.ajax({
      url: uploadUrl,
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      success: function (resp) {
        setStatus("Installed activity: " + resp.slug, "success");
        var $select = $(element).find("#pxc-activity-select");
        if ($select.find('option[value="' + resp.slug + '"]').length === 0) {
          $select.append(
            $("<option>").attr("value", resp.slug).text(resp.slug)
          );
        }
        $select.val(resp.slug);
      },
      error: function (xhr) {
        setStatus(
          "Upload failed: " + (xhr.responseText || xhr.statusText),
          "error"
        );
      },
      complete: function () {
        $button.removeClass("is-busy is-disabled");
      },
    });
  });
}
