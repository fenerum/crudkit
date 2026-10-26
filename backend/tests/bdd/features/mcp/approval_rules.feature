@mcp-tool:create_record @mcp-tool:update_record @mcp-tool:run_action
Feature: Sensitive changes wait for a person even with write access
  A project can mark fields and actions as needing a person's approval. An
  MCP client with write access still only proposes those changes; everything
  else it writes straight away.

  Background:
    Given the server lets MCP clients write directly
    And Alice can view, add and change customers
    And a customer "Acme" with status "active"
    And changes to the status of customers need a person's approval
    And running "Mark churned" needs approval
    And Alice connected the MCP client "Research Bot" with write access

  Scenario: An action that needs approval is proposed
    When an MCP client acting for Alice runs "Mark churned" on "Acme"
    Then the change waits for Alice's approval as "Run Mark churned"
    And "Acme" still has status "active"

  Scenario: A change touching an approval field is proposed as a whole
    When an MCP client acting for Alice updates "Acme" with:
      | name   | Acme Inc |
      | status | churned  |
    Then the change waits for Alice's approval
    And the proposal would make these changes:
      | name   | Acme Inc |
      | status | churned  |
    And "Acme" still has name "Acme"

  Scenario: A new record setting an approval field is proposed
    When an MCP client acting for Alice creates a customer "Globex" with:
      | status | churned |
    Then the change waits for Alice's approval as "Create customer"
    And no customer "Globex" exists

  Scenario: Everything else is written straight away
    When an MCP client acting for Alice changes the name of "Acme" to "Acme Inc"
    Then "Acme" has name "Acme Inc"
    And nothing waits for approval

  Scenario: Without the assistant app, changes that need approval are refused
    Given the assistant app is not installed
    When an MCP client acting for Alice runs "Mark churned" on "Acme"
    Then the client is refused with "This change needs approval, and approvals need crudkit_assistant installed"
    And "Acme" still has status "active"
