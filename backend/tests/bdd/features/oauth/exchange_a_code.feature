@endpoint:crudkit_mcp_oauth_token
Feature: An MCP client exchanges its code for tokens
  After a person allows access, the client trades the short-lived code for an
  access token (valid for an hour) and a refresh token (valid for 90 days).
  The code only works once, for the client it was given to, and only with the
  secret (the PKCE verifier) the client started with.

  Background:
    Given Alice is a user without any permissions
    And an MCP client "Claude" is registered
    And "Claude" holds an authorization code from Alice

  Scenario: A valid code is exchanged for an access token and a refresh token
    When "Claude" exchanges the authorization code
    Then "Claude" receives an access token for 1 hour and a refresh token for 90 days
    And the access token lets "Claude" act for Alice

  Scenario: The tokens carry the access Alice granted
    Given "Claude" holds an authorization code from Alice for "read propose"
    When "Claude" exchanges the authorization code
    Then "Claude" receives tokens for "read propose"

  Scenario: A code can only be used once
    Given "Claude" exchanged the authorization code
    When "Claude" exchanges the authorization code again
    Then the token request fails with "invalid_grant"

  Scenario: An expired code is refused
    Given the authorization code has expired
    When "Claude" exchanges the authorization code
    Then the token request fails with "invalid_grant"

  Scenario: The code of a person who has since been deactivated is refused
    Given Alice is inactive
    When "Claude" exchanges the authorization code
    Then the token request fails with "invalid_grant"

  Scenario Outline: A code is refused when the client cannot prove it is the one that asked
    When "Claude" exchanges the authorization code <how>
    Then the token request fails with "invalid_grant"

    Examples:
      | how                              |
      | with the wrong verifier          |
      | for a different redirect address |

  Scenario: Another client cannot use the code
    Given an MCP client "Other App" is registered
    When "Other App" exchanges the authorization code
    Then the token request fails with "invalid_grant"

  Scenario: A request without the verifier is incomplete
    When "Claude" exchanges the authorization code without the verifier
    Then the token request fails with "invalid_request"

  Scenario: Only codes and refresh tokens can be exchanged
    When "Claude" asks for a token with the grant type "client_credentials"
    Then the token request fails with "unsupported_grant_type"
