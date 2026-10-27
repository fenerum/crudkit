@mcp-tool:undo
Feature: An MCP client undoes a change
  Every write an MCP client makes reports its change set, so the client can
  undo it, or any other change the person could undo in the app, as long as
  nobody has changed the same fields since. Undoing a change to something that
  needs approval needs approval too.

  Background:
    Given the server lets MCP clients write directly
    And Alice can view and change customers
    And a customer "Acme" with status "active"
    And Alice connected an MCP client with write access

  Scenario: Undoing the client's own change puts the previous value back
    Given an MCP client acting for Alice changed the name of "Acme" to "Acme Inc"
    When an MCP client acting for Alice undoes that change
    Then the client is told it undid 1 change
    And "Acme" has name "Acme"

  Scenario: A change made in the app can be undone through MCP
    Given Alice changed the status of "Acme" to "churned"
    When an MCP client acting for Alice undoes that change
    Then "Acme" has status "active"

  Scenario: An undo through MCP can itself be undone through MCP
    Given an MCP client acting for Alice changed the name of "Acme" to "Acme Inc"
    And an MCP client acting for Alice undid that change
    When an MCP client acting for Alice undoes that change
    Then "Acme" has name "Acme Inc"

  Scenario: Undo reports a conflict when someone changed the same field since
    Given Bob can view and change customers
    And an MCP client acting for Alice changed the status of "Acme" to "churned"
    And Bob changed the status of "Acme" to "active"
    When an MCP client acting for Alice undoes her change
    Then the client is told the undo conflicts on the status of "Acme"
    And "Acme" still has status "active"

  Scenario: An MCP client can force an undo over a conflicting change
    Given Bob can view and change customers
    And an MCP client acting for Alice changed the name of "Acme" to "Acme Inc"
    And Bob changed the name of "Acme" to "Acme Ltd"
    When an MCP client acting for Alice undoes her change anyway
    Then the client is told it undid 1 change
    And "Acme" has name "Acme"

  Scenario: An MCP client cannot undo the same change twice
    Given an MCP client acting for Alice changed the name of "Acme" to "Acme Inc"
    And an MCP client acting for Alice undid that change
    When an MCP client acting for Alice undoes the same change again
    Then the client is refused with "already been reverted"

  Scenario: An MCP client cannot undo a change that never happened
    When an MCP client acting for Alice undoes a change that never happened
    Then the client is refused with "Unknown change set"

  Scenario: Undoing a change to an approval field waits for a person
    Given changes to the status of customers need a person's approval
    And Alice changed the status of "Acme" to "churned"
    When an MCP client acting for Alice undoes that change
    Then the change waits for Alice's approval
    And "Acme" still has status "churned"
