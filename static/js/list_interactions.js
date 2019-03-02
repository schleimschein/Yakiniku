// Init list

(function() {

  var paginationList = document.getElementsByClassName("pagination")[0];
  if (List.matchingItems.length < List.page) {
    paginationList.classList.add('is-invisible');
  }

  // Init search function
  var searchField = document.getElementById("list-search-field");
  searchField.onkeyup = function() {
    var searchString = this.value;
    List.search(searchString);
  };


////////////////////////////////
// Sidebar-List interaction  //
////////////////////////////////

  var activeRow = null;
  var activeRowId = null;

  // Click event handler that marks clicked rows as active
  (function () {
    var clickHandler = function () {
      var row = this;
      var activeClassName = "list-row-active";

      if (activeRow) {
        if (row.classList)
          activeRow.classList.remove(activeClassName);
        else
          activeRow.className = activeRow.className.replace(new RegExp('(^|\\b)' + activeClassName.split(' ').join('|') + '(\\b|$)', 'gi'), ' ');
      }

      if (row.classList)
        row.classList.add(activeClassName);
      else
        row.className += ' ' + activeClassName;

      var id = row.querySelectorAll("." + listType + "-id")[0].innerHTML;
      activeRow = row;
      activeRowId = id.trim();
    };

    // Function that adds clickHandler to all elements with class "tag-row" as an EventListener on 'click'
    var clickHandlerAdder = function () {
	    var rows = document.getElementsByClassName(listType + "-row");
      for (var i = 0; i < rows.length; i++) {
      var current = rows[i];
      current.addEventListener('click', clickHandler, false);
    }};

    // Find all list rows and add the clickHandler as an EventListener
    clickHandlerAdder();

    // Every time a pagination link is clicked make sure to add clickHandler to all "new" elements
    var paginationLinks = paginationList.children;
    for (var i = 0; i < paginationLinks.length; i++) {
      paginationLinks[i].addEventListener('click', clickHandlerAdder);
    }


      })();

  // Handle delete option
  (function () {
    var clickHandler = function () {
      if (activeRowId) {
        if (confirm("Are you sure you want to delete " + listType + " " + activeRowId + "?")) {

          var url = "/admin/" + listType+'s' + "/delete";
          var data = {id: activeRowId};

          var httpRequest = new XMLHttpRequest();
          httpRequest.open('POST', url);
          httpRequest.setRequestHeader("Content-Type", "application/json");

          httpRequest.onload = function () {
            if (JSON.parse(httpRequest.response)["ok"] === true) {
              List.remove(listType + "-id", activeRowId);
              List.update();
            } else {
              location.reload(true);
            }
          };

          httpRequest.onerror = function () {
            alert("Delete request contained an error");
          };

          httpRequest.send(JSON.stringify(data));
        }
      } else {
        alert("Select a " + listType + " delete.");
      }
    };

    var anchor = document.getElementById("action-delete-" + listType);
    anchor.addEventListener('click', clickHandler, false);
  })();

  // Handle edit option
  (function () {
    var clickHandler = function () {
      if (activeRowId) {

        var url = "/admin/" + listType+'s' + "/edit/" + activeRowId;
        window.location = url;

      } else {
        alert("Select a " + listType + " to edit!");
      }
    };

    var anchor = document.getElementById("action-edit-" + listType);
    anchor.addEventListener('click', clickHandler, false);
  })();

  // Show posts
  (function () {
    var clickHandler = function () {
      if (activeRowId) {
        var row = document.getElementsByClassName("list-row-active")[0];
        var nameColumnRow = row.querySelectorAll("." + listType + "-name")[0];
        var name = nameColumnRow.getAttribute("data-name").trim();
        var url = "/" + listType + "/" + name ;
        window.location = url;
      } else {
        alert("Select a " + listType + " to choose!");
      }
    };

    var anchor = document.getElementById("action-show-post-of-" + listType);
    if (typeof(anchor) != 'undefined' && anchor != null) {
      anchor.addEventListener('click', clickHandler, false);
    }
  })();
})();




