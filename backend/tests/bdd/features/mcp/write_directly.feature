@mcp-tool:create_record @mcp-tool:update_record @mcp-tool:run_action @mcp-tool:add_note
Feature: An MCP client writes directly
  Where the server allows it and the person granted write access, an MCP
  client creates and changes records, runs actions and adds notes straight
  away, with exactly the permissions of that person. Every change is recorded
  as made by the person through the named client.

  Background:
    Given the server lets MCP clients write directly
    And Alice can view, add and change customers
    And Alice can view topics
    And a topic "Billing"
    And a customer "Acme" with:
      | status | active  |
      | topic  | Billing |
    And Alice connected the MCP client "Research Bot" with write access

  Scenario: Creating a record
    When an MCP client acting for Alice creates a customer "Globex" with:
      | topic | Billing |
    Then there is now a customer "Globex"
    And "Globex" has topic "Billing"
    And "Globex" is recorded as created by Alice
    And the client sees the name "Globex"
    And the client's change is recorded as made by Alice through "Research Bot"

  Scenario: Creating needs permission to add
    When an MCP client acting for Alice creates a topic "Support"
    Then the client is refused with "Permission denied"
    And no topic "Support" exists

  Scenario: Changing a record
    When an MCP client acting for Alice changes the name of "Acme" to "Acme Inc"
    Then "Acme" has name "Acme Inc"
    And the client sees the name "Acme Inc"
    And the client's change is recorded as made by Alice through "Research Bot"

  Scenario Outline: Only writable fields can be changed
    When an MCP client acting for Alice updates "Acme" with:
      | <field> | <value> |
    Then the client is refused with "Unknown or read-only field(s): ['<name>']"

    Examples:
      | field      | value | name       |
      | nope       | 1     | nope       |
      | created by | Alice | created_by |
      | deleted    | true  | deleted    |

  Scenario: A link to a record that does not exist is refused, not cleared
    When an MCP client acting for Alice points the topic of "Acme" at a topic that does not exist
    Then the client is refused with "not found"
    And "Acme" still has topic "Billing"

  Scenario: Changing needs permission to change that record
    Given Bob can view customers
    And Bob connected an MCP client with write access
    When an MCP client acting for Bob changes the name of "Acme" to "Hacked"
    Then the client is refused with "not found, or not available for change"
    And "Acme" still has name "Acme"

  Scenario: Row rules for writing apply to MCP clients too
    Given people may only change the customers they are the owner of
    When an MCP client acting for Alice changes the name of "Acme" to "Acme Inc"
    Then the client is refused with "not available for change"
    And "Acme" still has name "Acme"

  Scenario: Running an action
    When an MCP client acting for Alice runs "Mark churned" on "Acme"
    Then "Acme" has status "churned"
    And the client's change is recorded as made by Alice through "Research Bot"

  Scenario: An action the record does not have is refused
    When an MCP client acting for Alice runs "delete_everything" on "Acme"
    Then the client is refused with "not available"

  Scenario: Adding a note
    When an MCP client acting for Alice adds the note "Renewal due" to "Acme"
    Then the note "Renewal due" is added to "Acme"

  Scenario: An empty note is refused
    When an MCP client acting for Alice adds the note "  " to "Acme"
    Then the client is refused with "Note body is empty"
    And "Acme" has no notes

  Scenario: Adding a note needs permission to change the record
    When an MCP client acting for Alice adds the note "Renewal due" to "Billing"
    Then the client is refused with "not available for change"
    And "Billing" has no notes

  Scenario: Notes cannot be added to CrudKit's own bookkeeping
    Given Alice can view views
    And Alice saved a view "Churned" of customers
    When an MCP client acting for Alice adds the note "Hello" to "Churned"
    Then the client is refused with "Unknown type 'VIW'"

  Scenario: A client with both propose and write access writes directly
    Given Alice connected the MCP client "Research Bot" with propose and write access
    When an MCP client acting for Alice changes the name of "Acme" to "Acme Inc"
    Then "Acme" has name "Acme Inc"
    And nothing waits for approval
