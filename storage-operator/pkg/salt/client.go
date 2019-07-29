package salt

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"time"

	"github.com/go-logr/logr"
	"github.com/pkg/errors"
	"sigs.k8s.io/controller-runtime/pkg/runtime/log"
)

// A Salt API client.
type Client struct {
	address string       // Address of the Salt API server.
	client  *http.Client // HTTP client to query Salt API.
	creds   *Credential  // Salt API authentication credentials.
	token   *authToken   // Salt API authentication token.
	logger  logr.Logger  // Logger for the client's requests
}

// Create a new Salt API client.
func NewClient(creds *Credential) *Client {
	const SALT_API_PORT int = 4507 // As defined in master-99-metalk8s.conf

	address := os.Getenv("METALK8S_SALT_MASTER_ADDRESS")
	if address == "" {
		address = "http://salt-master"
	}

	return &Client{
		address: fmt.Sprintf("%s:%d", address, SALT_API_PORT),
		client:  &http.Client{},
		creds:   creds,
		token:   nil,
		logger:  log.Log.WithName("salt_api"),
	}
}

// Test function, will be removed later…
func (self *Client) TestPing() (map[string]interface{}, error) {
	payload := map[string]string{
		"client": "local",
		"tgt":    "*",
		"fun":    "test.ping",
	}

	self.logger.Info("test.ping")

	ans, err := self.authenticatedPost("/", payload)
	if err != nil {
		return nil, errors.Wrap(err, "test.ping failed")
	}
	return ans, nil
}

// Send an authenticated POST request to Salt API.
//
// Automatically handle:
// - missing token (authenticate)
// - token expiration (re-authenticate)
// - token invalidation (re-authenticate)
//
// Arguments
//     endpoint: API endpoint.
//     payload:  POST JSON payload.
//
// Returns
//     The decoded response body.
func (self *Client) authenticatedPost(
	endpoint string, payload map[string]string,
) (map[string]interface{}, error) {
	// Authenticate if we don't have a valid token.
	if self.token == nil || self.token.isExpired() {
		if err := self.authenticate(); err != nil {
			return nil, err
		}
	}

	response, err := self.doPost(endpoint, payload, true)
	if err != nil {
		return nil, err
	}
	// Maybe the token got invalidated by a restart of the Salt API server.
	// => Re-authenticate and retry.
	if response.StatusCode == 401 {
		self.logger.Info("valid token rejected: try to re-authenticate")

		response.Body.Close() // Terminate this request before starting another.

		self.token = nil
		if err := self.authenticate(); err != nil {
			return nil, err
		}
		response, err = self.doPost(endpoint, payload, true)
	}
	defer response.Body.Close()

	return decodeApiResponse(response)
}

// Authenticate against the Salt API server.
func (self *Client) authenticate() error {
	payload := map[string]string{
		"eauth":      "kubernetes_rbac",
		"username":   self.creds.username,
		"token":      self.creds.token,
		"token_type": self.creds.kind,
	}

	self.logger.Info(
		"Auth", "username", payload["username"], "type", payload["token_type"],
	)

	response, err := self.doPost("/login", payload, false)
	if err != nil {
		return err
	}
	defer response.Body.Close()

	output, err := decodeApiResponse(response)
	if err != nil {
		return errors.Wrap(err, "Salt API authentication failed")
	}

	// TODO(#1461): make this more robust.
	self.token = newToken(
		output["token"].(string), output["expire"].(float64),
	)
	return nil
}

// Send a POST request to Salt API.
//
// Arguments
//     endpoint: API endpoint.
//     payload:  POST JSON payload.
//     is_auth:  Is the request authenticated?
//
// Returns
//     The POST response.
func (self *Client) doPost(
	endpoint string, payload map[string]string, is_auth bool,
) (*http.Response, error) {
	var response *http.Response = nil

	// Setup the translog.
	defer func(start time.Time) {
		elapsed := int64(time.Since(start) / time.Millisecond)
		self.logRequest("POST", endpoint, response, elapsed)
	}(time.Now())

	request, err := self.newPostRequest(endpoint, payload, is_auth)
	if err != nil {
		return nil, errors.Wrap(err, "cannot create POST request")
	}

	// Send the POST request.
	response, err = self.client.Do(request)
	if err != nil {
		return nil, errors.Wrap(err, "POST failed on Salt API")
	}
	return response, nil
}

// Log an HTTP request.
//
// Arguments
//     verb:     HTTP verb used for the request
//     endpoint: API endpoint.
//     response: HTTP response (if any)
//     elapsed:  response time (in ms)
func (self *Client) logRequest(
	verb string, endpoint string, response *http.Response, elapsed int64,
) {
	url := fmt.Sprintf("%s%s", self.address, endpoint)

	if response != nil {
		self.logger.Info(verb,
			"url", url, "StatusCode", response.StatusCode, "duration", elapsed,
		)
	} else {
		self.logger.Info(verb, "url", url, "duration", elapsed)
	}
}

// Create a POST request for Salt API.
//
// Arguments
//     endpoint: API endpoint.
//     payload:  POST JSON payload.
//     is_auth:  Is the request authenticated?
//
// Returns
//     The POST request.
func (self *Client) newPostRequest(
	endpoint string, payload map[string]string, is_auth bool,
) (*http.Request, error) {
	// Build target URL.
	url := fmt.Sprintf("%s%s", self.address, endpoint)

	// Encode the payload into JSON.
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, errors.Wrap(err, "cannot serialize POST body")
	}
	// Prepare the POST request.
	request, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, errors.Wrap(err, "cannot prepare POST query for Salt API")
	}

	request.Header.Set("Accept", "application/json")
	request.Header.Set("Content-Type", "application/json")
	if is_auth {
		request.Header.Set("X-Auth-Token", self.token.value)
	}
	return request, nil
}

// Decode the POST response payload.
//
// Arguments
//     response: the POST response.
//
// Returns
//     The decoded API response.
func decodeApiResponse(response *http.Response) (map[string]interface{}, error) {
	// Check the return code before trying to decode the body.
	if response.StatusCode != 200 {
		errmsg := fmt.Sprintf(
			"Salt API failed with code %d", response.StatusCode,
		)
		// No decode: Salt API may returns HTML even when you asked for JSON…
		buf, err := ioutil.ReadAll(response.Body)
		if err == nil {
			errmsg = fmt.Sprintf("%s: %s", errmsg, string(buf))
		}
		return nil, errors.New(errmsg)
	}
	// Decode the response body.
	var result map[string]interface{}
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		return nil, errors.Wrap(err, "cannot decode Salt API response")
	}
	// The real result is in a single-item list stored in the `return` field.
	// TODO(#1461): make this more robust.
	return result["return"].([]interface{})[0].(map[string]interface{}), nil
}