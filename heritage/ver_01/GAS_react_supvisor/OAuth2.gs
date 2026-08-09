/**
 * OAuth2.gs - Standalone Google Apps Script OAuth2 Library Implementation
 * Based on Google Workspace Apps Script OAuth2 Library:
 * https://github.com/googleworkspace/apps-script-oauth2
 *
 * Allows calling OAuth2.createService(serviceName) directly without adding external Apps Script Library IDs.
 */

var OAuth2 = {
  createService: function(serviceName) {
    return new Service_(serviceName);
  },

  getRedirectUri: function(scriptId) {
    if (!scriptId) {
      scriptId = ScriptApp.getScriptId();
    }
    return 'https://script.google.com/macros/d/' + encodeURIComponent(scriptId) + '/usercallback';
  }
};

/**
 * Service_ Constructor
 */
function Service_(serviceName) {
  if (!serviceName) {
    throw new Error('Service name is required.');
  }
  this.serviceName_ = serviceName;
  this.authorizationBaseUrl_ = '';
  this.tokenUrl_ = '';
  this.clientId_ = '';
  this.clientSecret_ = '';
  this.callbackFunctionName_ = '';
  this.propertyStore_ = PropertiesService.getUserProperties();
  this.scope_ = '';
  this.params_ = {};
  this.grantType_ = 'authorization_code';
}

Service_.prototype.setAuthorizationBaseUrl = function(url) {
  this.authorizationBaseUrl_ = url;
  return this;
};

Service_.prototype.setTokenUrl = function(url) {
  this.tokenUrl_ = url;
  return this;
};

Service_.prototype.setClientId = function(clientId) {
  this.clientId_ = clientId;
  return this;
};

Service_.prototype.setClientSecret = function(clientSecret) {
  this.clientSecret_ = clientSecret;
  return this;
};

Service_.prototype.setCallbackFunction = function(callbackFunctionName) {
  this.callbackFunctionName_ = callbackFunctionName;
  return this;
};

Service_.prototype.setPropertyStore = function(propertyStore) {
  this.propertyStore_ = propertyStore;
  return this;
};

Service_.prototype.setScope = function(scope) {
  this.scope_ = scope;
  return this;
};

Service_.prototype.setParam = function(key, value) {
  this.params_[key] = value;
  return this;
};

Service_.prototype.setGrantType = function(grantType) {
  this.grantType_ = grantType;
  return this;
};

Service_.prototype.getPropertyKey_ = function() {
  return 'oauth2.' + this.serviceName_;
};

Service_.prototype.saveToken_ = function(tokenData) {
  if (this.propertyStore_) {
    var key = this.getPropertyKey_();
    var value = JSON.stringify(tokenData);
    this.propertyStore_.setProperty(key, value);
  }
};

Service_.prototype.getToken = function() {
  if (!this.propertyStore_) return null;
  var key = this.getPropertyKey_();
  var value = this.propertyStore_.getProperty(key);
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch (e) {
    return null;
  }
};

Service_.prototype.hasAccess = function() {
  var token = this.getToken();
  if (!token) return false;
  if (token.expires_at) {
    var now = Math.floor(Date.now() / 1000);
    if (now >= token.expires_at - 60) {
      return this.refresh_();
    }
  }
  return true;
};

Service_.prototype.getAccessToken = function() {
  if (!this.hasAccess()) {
    return null;
  }
  var token = this.getToken();
  return token ? token.access_token : null;
};

Service_.prototype.getAuthorizationUrl = function(opt_extraParams) {
  var redirectUri = OAuth2.getRedirectUri();
  var params = {
    client_id: this.clientId_,
    response_type: 'code',
    redirect_uri: redirectUri,
    state: this.getStateToken_(this.callbackFunctionName_)
  };

  if (this.scope_) {
    params.scope = Array.isArray(this.scope_) ? this.scope_.join(' ') : this.scope_;
  }

  for (var key in this.params_) {
    params[key] = this.params_[key];
  }

  if (opt_extraParams) {
    for (var extraKey in opt_extraParams) {
      params[extraKey] = opt_extraParams[extraKey];
    }
  }

  var url = this.authorizationBaseUrl_;
  var queryString = Object.keys(params).map(function(k) {
    return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]);
  }).join('&');

  return url + (url.indexOf('?') >= 0 ? '&' : '?') + queryString;
};

Service_.prototype.getStateToken_ = function(callbackFunctionName) {
  var state = {
    serviceName: this.serviceName_,
    callbackFunctionName: callbackFunctionName
  };
  return Utilities.base64Encode(JSON.stringify(state));
};

Service_.prototype.handleCallback = function(request) {
  var code = request.parameter.code;
  var error = request.parameter.error;

  if (error) {
    return false;
  }

  if (!code) {
    return false;
  }

  return this.fetchToken_(code);
};

Service_.prototype.fetchToken_ = function(code) {
  var redirectUri = OAuth2.getRedirectUri();
  var payload = {
    client_id: this.clientId_,
    client_secret: this.clientSecret_,
    code: code,
    redirect_uri: redirectUri,
    grant_type: 'authorization_code'
  };

  var options = {
    method: 'post',
    payload: payload,
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(this.tokenUrl_, options);
  var statusCode = response.getResponseCode();
  var result = JSON.parse(response.getContentText());

  if (statusCode >= 200 && statusCode < 300) {
    if (result.expires_in) {
      result.expires_at = Math.floor(Date.now() / 1000) + Number(result.expires_in);
    }
    this.saveToken_(result);
    return true;
  } else {
    return false;
  }
};

Service_.prototype.refresh_ = function() {
  var token = this.getToken();
  if (!token || !token.refresh_token) {
    return false;
  }

  var payload = {
    client_id: this.clientId_,
    client_secret: this.clientSecret_,
    refresh_token: token.refresh_token,
    grant_type: 'refresh_token'
  };

  var options = {
    method: 'post',
    payload: payload,
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(this.tokenUrl_, options);
  var statusCode = response.getResponseCode();
  var result = JSON.parse(response.getContentText());

  if (statusCode >= 200 && statusCode < 300) {
    result.refresh_token = result.refresh_token || token.refresh_token;
    if (result.expires_in) {
      result.expires_at = Math.floor(Date.now() / 1000) + Number(result.expires_in);
    }
    this.saveToken_(result);
    return true;
  } else {
    return false;
  }
};

Service_.prototype.reset = function() {
  if (this.propertyStore_) {
    var key = this.getPropertyKey_();
    this.propertyStore_.deleteProperty(key);
  }
};
