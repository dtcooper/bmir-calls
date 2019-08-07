/* BEGIN USER SERVICEABLE PARTS */
var SEND_DEBUG_EMAIL = false;
var DEBUG_EMAIL = 'user@example.com';
var API_PASSWORD = 'hackme';
var SUBMIT_URL = 'https://example.com/volunteers/submit';

// Item IDs for questions in form, use logItemIDs() in Apps Script to find these out
var ENABLED_ID = 111111;
var NAME_ID = 222222;
var PHONE_NUMBER_ID = 333333;
var OPT_IN_HOURS_ID = 444444;
var TIMEZONE_ID = 555555;
var COMMENTS_ID = 666666;
/* END USER SERVICEABLE PARTS */

function logItemIDs() {
  // helper to log the form question IDs
  var items = FormApp.getActiveForm().getItems();
  for (var i = 0; i < items.length; i++) {
    var item = items[i]
    Logger.log('"' + item.getTitle() + '" -- ' + item.getId());
  }
}

function getAnswer(response, itemId) {
  var item = FormApp.getActiveForm().getItemById(itemId);
  var response = response.getResponseForItem(item);
  return response ? response.getResponse() : null;
}

function parseFormResponse(response) {
  return {
    'email': response.getRespondentEmail(),
    'enabled': getAnswer(response, ENABLED_ID).toLowerCase().indexOf('yes') == 0,
    'name': getAnswer(response, NAME_ID),
    'phone_number': getAnswer(response, PHONE_NUMBER_ID),
    'opt_in_hours': getAnswer(response, OPT_IN_HOURS_ID),
    'timezone': getAnswer(response, TIMEZONE_ID),
    'comments': getAnswer(response, COMMENTS_ID)
  };
}

function post(data) {
  var options = {
    'method' : 'post',
    'contentType': 'application/json',
    'payload': JSON.stringify(data)
  };

  if (SEND_DEBUG_EMAIL) {
    MailApp.sendEmail(
      'dave@kupesoft.com', 'BMIR Calls Form Submit Debug',
      JSON.stringify(data, null, 2));
  }

  UrlFetchApp.fetch(
    SUBMIT_URL + '?password=' + encodeURIComponent(API_PASSWORD),
    options);
}

function onSubmit(e) {
    post(parseFormResponse(e.response));
}
