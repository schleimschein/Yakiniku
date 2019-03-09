// Event listener that handels the bulma navbar burger. As provided in the bulma documentation

document.addEventListener('DOMContentLoaded', function () {
    // Get all "navbar-burger" elements
    var $navbarBurgers = Array.prototype.slice.call(document.querySelectorAll('.navbar-burger'), 0);

    var $navbarSearchControl = document.getElementById('navbar-search-control');
    var $navbarSearchInput = document.getElementById('navbar-search-input');

    // Check if there are any navbar burgers
    if ($navbarBurgers.length > 0) {

      // Add a click event on each of them
      $navbarBurgers.forEach(function ($el) {
        $el.addEventListener('click', function () {

          // Get the target from the "data-target" attribute
          var target = $el.dataset.target;
          var $target = document.getElementById(target);

          // Toggle the class on both the "navbar-burger" and the "navbar-menu"
          $el.classList.toggle('is-active');
          $target.classList.toggle('is-active');

          $navbarSearchControl.classList.toggle('navbar-burger-is-active');
          $navbarSearchInput.classList.toggle('navbar-burger-is-active');
        });
      });
    }
  });