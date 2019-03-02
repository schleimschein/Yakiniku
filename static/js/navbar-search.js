(function() {
  var searchForm = document.getElementById('navbar_search_form');
  var searchControl = document.getElementById('navbar-search-control');
  var searchInput = document.getElementById('navbar-search-input');
  var searchIcon = document.getElementById('navbar-search-icon');

  searchInput.onkeyup = function (e) {
    if (searchInput.value.trim() !== "") {
      searchIcon.style.pointerEvents = "auto";
    } else if (searchInput.value.trim() === "") {
      searchIcon.style.pointerEvents = "none";
    }

    if (e.keyCode == 27) {//27 is the code for escape
      searchInput.blur();
    }
  };

  searchInput.onblur = function (e) {
    if ((e.relatedTarget === searchIcon) && searchInput.value.trim() !== "") {
      searchForm.submit();
    } else {
      searchIcon.style.pointerEvents = "none";
    }
  };

  searchInput.onfocus = function (e) {
    if (searchInput.value.trim() !== "") {
      searchIcon.style.pointerEvents = "auto";
    }
  };
})();