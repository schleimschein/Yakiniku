(function() {
  var deleteContainers  = document.getElementsByClassName('has-delete');

  for(var i = 0; i < deleteContainers.length; i++)
  {
      var deleteContainer = deleteContainers[i];
      var deletes = deleteContainer.getElementsByClassName('delete');

      for(var i = 0; i < deletes.length; i++)
      {
        var dlt = deletes[i];

        dlt.onclick = function()
        {
            deleteContainer.remove();
        }
      }
  }
})();