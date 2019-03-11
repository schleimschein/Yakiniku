(function() {

  // Form Elements
  var postForm = document.getElementById('post-form');
  var postFormTitle = document.getElementById("post-form-title");
  var postFormTags = document.getElementById('post-form-tags');
  var postFormPublishSwitch = document.getElementById('post-form-publish-switch');
  var postFormPublishSwitchLabel = document.getElementById('post-form-publish-switch-label');
  var postFormSubmitButton = document.getElementById('post-form-submit-button');

  // Preview Elements
  var postPreview =  document.getElementById("preview");
  var postPreviewBox = document.getElementById("preview-box");
  var postPreviewHeading = document.getElementsByClassName("post-heading")[0];
  //var postPreviewCurrentDateTime = document.getElementByClassName("current-date-time")[0];
  var postPreviewContent = document.getElementsByClassName("post-content")[0];
  var postPreviewTags = document.getElementsByClassName("post-tags")[0];



  ////////////////////////////////
  //  Sidebar-Form interaction  //
  ////////////////////////////////

  // Save as draft option
  (function() {
   var clickHandler = function () {
     postFormPublishSwitch.checked = false;
     postForm.submit();
   };

   var anchor = document.getElementById("action-draft");
   anchor.addEventListener('click', clickHandler, false);
  })();

  // Preview option
  (function() {
   var clickHandler = function () {
     var postFormData = { };
     postFormData.title = postFormTitle.value.trim();
     postFormData.content_markdown = postFormEditor.value();
     postFormData.tags = postFormTags.value.trim().split(',');

     // Http request: Flask translates markdown into html
     var url = "/admin/preview";
     var httpRequest = new XMLHttpinput-tagifyRequest();
     httpRequest.open('POST', url);
     httpRequest.setRequestHeader("Content-Type", "application/json");
     // If http request is success, set post title, description, content & tags and unhide it to preview

     httpRequest.onload = function () {
       var postPreviewContent_html = JSON.parse(httpRequest.response)["html"];

       postPreviewHeading.innerHTML = postFormData.postTitle;
       postPreviewContent.innerHTML = postPreviewContent_html;
       for (var i = 0; i < postFormData.tags.length; i++) {
         var postPreviewTag_html = '<a class="level-item tag is-primary post-tag">' + postFormData.tags[i] + '</a>';
         postPreviewTags.insertAdjacentHTML('beforeend', postPreviewTag_html);
       }

       postPreview.style.display = "block";
       postPreviewBox.scrollIntoView();
//     let  dateTime = JSON.parse(httpRequest.response)["date_time"];
//     postPreviewCurrentDateTime.innerHTML = dateTime;
        };
     httpRequest.onerror = function () {
          alert("Request contained an error");
        };
     httpRequest.send(JSON.stringify(postFormData));
   };

   var anchor = document.getElementById("action-preview");
   anchor.addEventListener('click', clickHandler, false);
 })();

  // Delete option
  (function() {
    var clickHandler = function () {
      var editId = document.getElementsByName("post-edit-id")[0];
        if (typeof(editId) !== 'undefined' && editId != null) {
          editId = editId.value.trim();
          if (confirm("Are you sure you want to delete post " + editId + "?")) {
            var url = "/admin/posts/delete";
            var data = JSON.stringify({id: editId, was_edit: true});

            var httpRequest = new XMLHttpRequest();
            httpRequest.open('POST', url);
            httpRequest.setRequestHeader("Content-Type", "application/json");

            httpRequest.onload = function () {
              if (JSON.parse(httpRequest.response)["ok"] === true) {
                window.location = "/admin/posts";
              } else {
                location.reload(true);
              }
            };

            httpRequest.onerror = function () {
              alert("Delete request contained an error");
            };

            httpRequest.send(data);
          }
        } else {
          window.location = "/admin/posts";
        }
   };

    var anchor = document.getElementById("action-delete-post");
    anchor.addEventListener('click', clickHandler, false);
 })();

  // Change submit button label in dependence of publish switch state   
  (function() {
   var clickHandler = function () {
      postFormSubmitButton.innerHTML = postFormPublishSwitch.checked ? "Post" : "Save";
      postFormPublishSwitchLabel.innerHTML = postFormPublishSwitch.checked ? "Publish" : "Draft";
   };

   var anchor = document.getElementById("post-form-publish-switch");
   anchor.addEventListener('click', clickHandler, false);
 })();

})();
