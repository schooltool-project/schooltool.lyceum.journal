var selected_cell = null;
var old_grade = null;
var grade = null;

function saveLessonDescription(value, event_id) {
    $.ajax({
       url: here + 'setLessonDescription.xml',
       type: 'POST',
       timeout: 5000,
       data: {event_id: event_id,
              lesson_description: value},
       error: function() {},
       success: function(xml){}
    });
}

function savePublicDescription(value, event_id) {
    $.ajax({
       url: here + 'setPublicDescription.xml',
       type: 'POST',
       timeout: 5000,
       data: {event_id: event_id,
              lesson_description: value},
       error: function() {},
       success: function(xml){}
    });
}

function FCKeditor_OnComplete(editorInstance)
{
  editorInstance.Events.AttachEvent("OnBlur", function () {
    var elem = document.getElementById(editorInstance.Name);
    if (editorInstance.Name == 'field.teacher_description')
        saveLessonDescription(editorInstance.GetXHTML(), elem.event_id);
    if (editorInstance.Name == 'field.public_description')
        savePublicDescription(editorInstance.GetXHTML(), elem.event_id);
  });
}

function unselectCell() {
    if (selected_cell) {
      var cell = selected_cell;

      if (grade != old_grade) {
        $.ajax({
           url: here + 'ajax.xml',
           type: 'POST',
           timeout: 5000,
           data: {event_id: cell.event_id,
                  person_id: cell.person_id,
                  grade: grade},
           error: function() {
             $(cell).css('background', '#FFAAAA');
             cell.modified_failure = true;
           },
           success: function(xml){
             $(cell).css('background', '#AAFFAA');
             cell.modified_success = true;
           }
        });
      }
      $(cell).removeClass('selected-cell');

      selected_cell = null;
      old_grade = null;
      grade = null;
    }
}

function selectCell(cell) {
  unselectCell();
  //var value = $.trim(cell.textContent);
  var value = $.trim(cell.innerHTML);
  old_grade = value;
  grade = value;
  $(cell).addClass('selected-cell');
  selected_cell = cell;
}

$(document).ready(function(){

  $(".data").click(function(event){
     if (event.target.person_id &&
         event.target.event_id)
     {
         if (selected_cell != event.target) {
           selectCell(event.target);
           return false;
         }
     }
  });

  $(".select-column").click(function(event){
    var cell_index = this.parentNode.cellIndex;

    $(".gradebook .data .selected-column").removeClass('selected-column');
    $(".gradebook .data .selected-row").removeClass('selected-row');

    $(".gradebook .data TR").each(function (index) {
       var cell = this.getElementsByTagName('td')[cell_index];
       if (cell) {
         $(cell).addClass("selected-column");
       }
    });


    var event_id = null;
    var inputs = $(event.target.parentNode).children(".event_id");
    if (inputs.length > 0) {
       event_id = inputs[0].value;
    }

    $.ajax({
       url: here + 'getLessonDescription.xml',
       type: 'POST',
       timeout: 5000,
       data: {event_id: event_id},
       error: function() {},
       success: function(xml){
           $('.lesson-description').html(xml);
       }
    });

    return false;
  });

  $(".select-column").each(function (index) {
    $(this).css('cursor', 'pointer');
    if ($(this).children().length > 0) {
      $(this).html($($(this).children()[0]).html());
    }
  });

  $(".select-row").click(function (event) {
    $(".gradebook .data .selected-column").removeClass('selected-column');
    $(".gradebook .data .selected-row").removeClass('selected-row');

    $(event.target.parentNode.parentNode).children("TD").each(function (index) {
       if (this.event_id && this.person_id) {
         $(this).addClass("selected-row");
       }
    });

    return false;
  });

  $(document).keydown(function (event) {
    if (selected_cell && !event.ctrlKey && !event.altKey) {
      if (event.which == 37) { // left
        index = selected_cell.cellIndex;
        tr = selected_cell.parentNode;
        new_td = tr.getElementsByTagName('td')[index-1];
        if (new_td.event_id && new_td.person_id) {
          selectCell(new_td);
          return false;
        }
      }

      if (event.which == 38) { // up
        index = selected_cell.cellIndex;
        tr = selected_cell.parentNode;

        next_tr = null;
        next_tr = tr.previousSibling;
        if (next_tr.nodeName != 'TR')
          next_tr = next_tr.previousSibling;

        if (!next_tr) return true;

        new_td = next_tr.getElementsByTagName('td')[index];

        if (new_td.event_id && new_td.person_id) {
          selectCell(new_td);
          return false;
        }
      }

      if (event.which == 39) { // right
        index = selected_cell.cellIndex;
        tr = selected_cell.parentNode;

        new_td = tr.getElementsByTagName('td')[index+1];

        if (new_td.event_id && new_td.person_id) {
          selectCell(new_td);
          return false;
        }
      }

      if (event.which == 40) { // down
        index = selected_cell.cellIndex;
        tr = selected_cell.parentNode;

        next_tr = tr.nextSibling;
        if (next_tr.nodeName != 'TR')
          next_tr = next_tr.nextSibling;

        if (!next_tr) return true;

        new_td = next_tr.getElementsByTagName('td')[index];
        if (new_td.event_id && new_td.person_id) {
          selectCell(new_td);
          return false;
        }
      }

      if (event.which == 8 || event.which == 46) { // Backspace, Del
        grade = '';
        $(selected_cell).html(grade);
        return false;
      }
    }
  });

  $(document).keypress(function (event) {
    if (selected_cell && !event.ctrlKey && !event.altKey) {
      //absent is n or N, tardy is p or P
      var keys = {enter: event.which == 13,
                  escape: event.which == 27,
                  space: event.which == 32,
                  absent: event.which == 78 || event.which == 110,
                  tardy: event.which == 80 || event.which == 112,
                  0: event.which == 48,
                  1: event.which == 49,
                  2: event.which == 50,
                  3: event.which == 51,
                  4: event.which == 52,
                  5: event.which == 53,
                  6: event.which == 54,
                  7: event.which == 55,
                  8: event.which == 56,
                  9: event.which == 57,
                  }

      if (keys.enter) { // enter
        var selection = $(".selected-column");
        var selected_rows = $(".selected-row");

        if (selected_rows.length > selection.length) {
          selection = selected_rows;
        }

        var item = 0;
        if (selection.length != 0) {
          selection.each(function (index) {
            if (this == selected_cell) {
              item = index + 1;
            }
          });
          unselectCell();
          if (item < selection.length)
            selectCell(selection[item]);
        } else {
          unselectCell();
        }
        return false;
      }

      if (keys.escape) { // esc
        grade = old_grade;
        $(selected_cell).html(grade);
        unselectCell();
        return false;
      }

      if (keys.space) { // Space
        grade = '';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['1']) { // 1
        grade = '1';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['2']) { // 2
        grade = '2';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['3']) { // 3
        grade = '3';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['4']) { // 4
        grade = '4';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['5']) { // 5
        grade = '5';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['6']) { // 6
        grade = '6';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['7']) { // 7
        grade = '7';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['8']) { // 8
        grade = '8';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['9']) { // 9
        grade = '9';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys['0']) { // 0
        grade = '10';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys.absent) { // N, n
        grade = 'n';
        $(selected_cell).html(grade);
        return false;
      }

      if (keys.tardy) { // P, p
        grade = 'p';
        $(selected_cell).html(grade);
        return false;
      }

    }
    return true;
  });

  table = $('.data')[0];
  rows = table.getElementsByTagName('tr');
  var event_ids = Array();
  for (var i = 0; i < rows.length; i++) {
    row = rows[i];
    if (i == 0) {
      cells = row.getElementsByTagName('th');
      for (var j = 0; j < cells.length; j++) {
        cell = cells[j];

        inputs = $(cells[j]).children(".event_id");
        if (inputs.length > 0) {
          event_ids[j] = inputs[0].value;
        }
      }
    }
    else
    {
      cells = row.getElementsByTagName('td');

      var person_id = null;
      if (cells.length > 0) {
        inputs = $(cells[0]).children(".person_id");
        if (inputs.length > 0) {
          person_id = inputs[0].value;
        }
      }
      for (var j = 0; j < cells.length; j++) {
        cell = cells[j];
        cell.person_id = person_id;
        cell.event_id = event_ids[j];
      }
    }
  }

  $(".data INPUT").each(function (index) {
    if (this.type == 'text') {
      $(this.parentNode).html(this.value);
    }
  });

});
