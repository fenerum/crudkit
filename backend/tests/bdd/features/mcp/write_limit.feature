@endpoint:crudkit_mcp
Feature: MCP clients may only write so fast
  A runaway AI tool should not be able to rewrite the whole database in a
  minute. Each client token may make a limited number of write calls per
  period (60 a minute unless the project says otherwise). Failed writes count
  too; reading is never limited.

  Background:
    Given the server lets MCP clients write directly
    And Alice can view and change customers
    And a customer "Acme"
    And Alice connected an MCP client with write access

  Scenario: Writes over the limit are refused
    Given MCP clients may make 2 writes per minute
    And an MCP client acting for Alice changed the name of "Acme" to "B"
    And an MCP client acting for Alice changed the name of "Acme" to "C"
    When an MCP client acting for Alice changes the name of "Acme" to "D"
    Then the client is refused with "Write rate limit exceeded: at most 2 writes per minute. Try again shortly."
    And "Acme" still has name "C"

  Scenario: Failed writes count against the limit
    Given MCP clients may make 1 write per minute
    And an MCP client acting for Alice changed the nope of "Acme" to "1"
    When an MCP client acting for Alice changes the name of "Acme" to "B"
    Then the client is refused with "Write rate limit exceeded"
    And "Acme" still has name "Acme"

  Scenario: Reading does not count against the limit
    Given MCP clients may make 1 write per minute
    When an MCP client acting for Alice opens "Acme"
    And an MCP client acting for Alice opens "Acme"
    And an MCP client acting for Alice changes the name of "Acme" to "B"
    Then "Acme" has name "B"

  Scenario: Each client has its own limit
    Given MCP clients may make 1 write per minute
    And Bob can view and change customers
    And Bob connected an MCP client with write access
    And an MCP client acting for Alice changed the name of "Acme" to "B"
    When an MCP client acting for Bob changes the name of "Acme" to "C"
    Then "Acme" has name "C"

  Scenario: Without a cache that can count, writes are not limited
    Given MCP clients may make 1 write per minute
    And the server's cache stores nothing
    And an MCP client acting for Alice changed the name of "Acme" to "B"
    When an MCP client acting for Alice changes the name of "Acme" to "C"
    Then "Acme" has name "C"
