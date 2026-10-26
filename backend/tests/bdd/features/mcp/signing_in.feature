@endpoint:crudkit_mcp
Feature: MCP clients sign in with an access token
  Every MCP request carries the access token a person granted. A client
  without a valid token is told where to find out how to sign in, so it can
  start the OAuth flow by itself. What the client may do comes from the token.

  Background:
    Given Alice is a user without any permissions

  Scenario: A client with a valid token is let in
    Given Alice connected an MCP client with read access
    When an MCP client acting for Alice starts a session
    Then it succeeds

  Scenario: A client without a token is told how to sign in
    When an MCP client starts a session without signing in
    Then it requires signing in
    And the client is told where to find out how to sign in

  Scenario: A made-up token is refused
    When an MCP client starts a session with a made-up token
    Then it requires signing in
    And the client is told where to find out how to sign in

  Scenario: An expired token is refused
    Given Alice connected an MCP client with read access
    And Alice's MCP token has expired
    When an MCP client acting for Alice starts a session
    Then it requires signing in

  Scenario: The token of a deactivated person is refused
    Given Alice connected an MCP client with read access
    And Alice is inactive
    When an MCP client acting for Alice starts a session
    Then it requires signing in

  Scenario: The token of a deactivated client is refused
    Given Alice connected the MCP client "Research Bot" with read access
    And the MCP client "Research Bot" has been deactivated
    When an MCP client acting for Alice starts a session
    Then it requires signing in

  Scenario: A token that does not grant reading cannot call tools
    Given Alice connected an MCP client without any access
    When an MCP client acting for Alice searches for "acme"
    Then the client is refused with "Insufficient scope: 'read' required"
