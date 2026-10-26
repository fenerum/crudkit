@endpoint:crudkit_mcp
Feature: Speaking the MCP protocol
  AI tools such as Claude talk to CrudKit over the Model Context Protocol.
  The server answers the handshake, pings and notifications the way MCP
  clients expect, and reports malformed messages as JSON-RPC errors instead of
  failing.

  Background:
    Given Alice is a user without any permissions

  Scenario: Starting a session agrees on a protocol version and names the server
    When an MCP client acting for Alice starts a session
    Then the server agrees on protocol version "2025-03-26"
    And the server introduces itself as "crudkit"
    And the reply says which protocol version the server speaks

  Scenario Outline: The server speaks the client's protocol version if it knows it
    When an MCP client acting for Alice starts a session asking for protocol version "<asked>"
    Then the server agrees on protocol version "<agreed>"

    Examples:
      | asked      | agreed     |
      | 2025-03-26 | 2025-03-26 |
      | 2025-06-18 | 2025-06-18 |
      | 2024-11-05 | 2025-03-26 |

  Scenario: A project can give its server its own name
    Given the MCP server is called "acme-crm"
    When an MCP client acting for Alice starts a session
    Then the server introduces itself as "acme-crm"

  @endpoint:crudkit_mcp_noslash
  Scenario: The server answers whether or not the address ends in a slash
    When an MCP client acting for Alice starts a session at the address without a trailing slash
    Then it succeeds
    And the server agrees on protocol version "2025-03-26"

  Scenario: The server answers pings
    When an MCP client acting for Alice pings the server
    Then the server answers the ping

  Scenario Outline: Notifications are accepted without a reply
    When an MCP client acting for Alice sends the notification "<notification>"
    Then the server accepts it without a reply

    Examples:
      | notification              |
      | notifications/initialized |
      | notifications/cancelled   |

  Scenario: An unknown method is reported as such
    When an MCP client acting for Alice calls the method "unknown/method"
    Then the client is told the method "unknown/method" does not exist

  Scenario: Several requests in one batch are refused
    When an MCP client acting for Alice sends a batch of requests
    Then the client is told the request is invalid

  Scenario: A message the server cannot handle is reported as a server failure
    When an MCP client acting for Alice sends a tool call with malformed parameters
    Then the client is told the server failed to handle it

  Scenario: Calling a tool that does not exist is refused
    When an MCP client acting for Alice calls "nonexistent"
    Then the client is refused with "Unknown tool: nonexistent"

  Scenario: Opening the event stream gives an empty stream
    When an MCP client opens the event stream
    Then the client receives an empty event stream
