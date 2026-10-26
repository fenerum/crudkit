@mcp-tool:create_record @mcp-tool:update_record @mcp-tool:run_action @mcp-tool:add_note @mcp-tool:undo
Feature: An MCP client proposes changes
  A person can let an AI tool suggest changes without letting it make them:
  with propose access, every write becomes a proposal in that person's Inbox,
  marked as coming from the client, and nothing changes until they confirm.

  Background:
    Given Alice can view, add and change customers
    And a customer "Acme" with status "active"
    And Alice connected the MCP client "Research Bot" with propose access

  Scenario: A change is proposed instead of made
    When an MCP client acting for Alice changes the name of "Acme" to "Acme Inc"
    Then the change waits for Alice's approval
    And the proposal comes from the MCP client "Research Bot"
    And the proposal would make these changes:
      | name | Acme Inc |
    And "Acme" still has name "Acme"

  Scenario: Confirming the proposal makes the change
    Given an MCP client acting for Alice changed the name of "Acme" to "Acme Inc"
    When Alice confirms the proposal
    Then "Acme" has name "Acme Inc"
    And the change to "Acme" is recorded as made by Alice through the MCP client "Research Bot"

  Scenario: A new record is proposed instead of created
    When an MCP client acting for Alice creates a customer "Globex"
    Then the change waits for Alice's approval as "Create customer"
    And no customer "Globex" exists

  Scenario: An action is proposed instead of run
    When an MCP client acting for Alice runs "Mark churned" on "Acme"
    Then the change waits for Alice's approval as "Run Mark churned"
    And "Acme" still has status "active"

  Scenario: A note is proposed instead of added
    When an MCP client acting for Alice adds the note "Called them" to "Acme"
    Then the change waits for Alice's approval as "Add note: Called them"
    And "Acme" has no notes

  Scenario: An undo is proposed instead of made
    Given Alice changed the status of "Acme" to "churned"
    When an MCP client acting for Alice undoes that change
    Then the change waits for Alice's approval
    And "Acme" still has status "churned"

  Scenario Outline: Writes that could never succeed are refused rather than proposed
    When an MCP client acting for Alice <attempt>
    Then the client is refused with "<message>"
    And nothing waits for approval

    Examples:
      | attempt                                       | message                      |
      | changes the nope of "Acme" to "1"             | Unknown or read-only field(s) |
      | runs "Delete everything" on "Acme"            | not available                |
      | adds the note "  " to "Acme"                  | Note body is empty           |

  Scenario: Proposing needs the same permission as making the change
    Given Bob can view customers
    And Bob connected an MCP client with propose access
    When an MCP client acting for Bob changes the name of "Acme" to "Acme Inc"
    Then the client is refused with "not available for change"
    And nothing waits for approval
