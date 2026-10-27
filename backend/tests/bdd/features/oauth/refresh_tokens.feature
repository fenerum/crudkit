@endpoint:crudkit_mcp_oauth_token
Feature: An MCP client refreshes its tokens
  Access tokens last an hour, so clients swap their refresh token for a new
  pair. Every refresh token works once: presenting one that was already used
  means it may have been stolen, so every token descended from the same sign-in
  stops working.

  Background:
    Given Alice is a user without any permissions
    And an MCP client "Claude" is registered
    And "Claude" holds tokens from Alice for "read propose"

  Scenario: Refreshing gives a new pair and retires the old refresh token
    When "Claude" refreshes its tokens
    Then "Claude" receives a new pair of tokens
    And "Claude" receives tokens for "read propose"
    And the earlier refresh token of "Claude" no longer works
    And the access token lets "Claude" act for Alice

  Scenario: Reusing a refresh token stops every token from that sign-in
    Given "Claude" refreshed its tokens
    When "Claude" refreshes with its first refresh token again
    Then the token request fails with "invalid_grant"
    And none of the refresh tokens of "Claude" work any more

  Scenario: An expired refresh token is refused
    Given the refresh token of "Claude" has expired
    When "Claude" refreshes its tokens
    Then the token request fails with "invalid_grant"

  Scenario: Deactivating a person stops their refresh tokens for good
    Given Alice is inactive
    When "Claude" refreshes its tokens
    Then the token request fails with "invalid_grant"
    And none of the refresh tokens of "Claude" work any more

  Scenario: A client cannot refresh another client's tokens
    Given an MCP client "Other App" is registered
    When "Other App" refreshes the tokens of "Claude"
    Then the token request fails with "invalid_client"

  Scenario: A deactivated client cannot refresh
    Given the MCP client "Claude" has been deactivated
    When "Claude" refreshes its tokens
    Then the token request fails with "invalid_client"

  Scenario: A client may narrow its access when refreshing
    When "Claude" refreshes its tokens narrowed to "read"
    Then "Claude" receives tokens for "read"

  Scenario: A client cannot widen its access when refreshing
    When "Claude" refreshes its tokens narrowed to "read write"
    Then the token request fails with "invalid_scope"

  Scenario: An unknown refresh token is refused
    When "Claude" refreshes with a made-up refresh token
    Then the token request fails with "invalid_grant"

  Scenario: A refresh without a refresh token is incomplete
    When "Claude" refreshes without a refresh token
    Then the token request fails with "invalid_request"
