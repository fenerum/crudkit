@transactional @websocket:ws/changes/
Feature: Signing in on the change stream
  Browsers that are not signed in with a session sign in on the change
  stream by sending their token first. Anything else closes the stream, so
  no-one can listen in without signing in.

  Background:
    Given Alice can view customers
    And someone connects to the change stream without signing in

  Scenario Outline: A stream that does not sign in properly is closed
    When they <attempt>
    Then the change stream tells them "<message>"
    And the change stream closes because signing in failed

    Examples:
      | attempt                              | message        |
      | send a message that is not a sign-in | Auth required. |
      | sign in without a token              | Missing token. |
      | sign in with a forged token          | Invalid token. |

  Scenario: The token of an inactive user is refused
    Given Alice is inactive
    When they sign in with Alice's token
    Then the change stream tells them "Invalid token."
    And the change stream closes because signing in failed

  Scenario: A message that is not JSON is reported and the stream stays open
    When they send something that is not JSON
    Then the change stream tells them "Invalid JSON"
    And the change stream stays open

  Scenario: A stream that does not sign in in time is closed
    When someone connects to the change stream and stays silent for five seconds
    Then the change stream tells them "Auth timeout."
    And the change stream closes because signing in failed
