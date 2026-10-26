@mcp-tool:get_record
Feature: An MCP client opens a record
  Opening one record gives its fields, with linked records spelled out, its
  recent activity feed and change log, and the actions the person may run on
  it. A client can ask for only the parts it needs.

  Background:
    Given Alice can view customers
    And Alice can view topics
    And a topic "Billing"
    And a customer "Acme" with:
      | status | active  |
      | topic  | Billing |

  Scenario: Opening a record shows its fields and names linked records
    When an MCP client acting for Alice opens "Acme"
    Then the client sees the status "active"
    And the client sees the topic "Billing"

  Scenario: Opening a record shows its activity feed
    Given a note "Called them" was left on "Acme"
    When an MCP client acting for Alice opens "Acme"
    Then the client sees the note "Called them" in the feed

  Scenario: The feed shows the 20 most recent entries
    Given 25 notes were left on "Acme"
    When an MCP client acting for Alice opens "Acme"
    Then the client sees 20 notes in the feed

  Scenario: The change log needs permission to see change logs
    When an MCP client acting for Alice opens "Acme"
    Then the client does not see the change log

  Scenario: The change log shows the 10 most recent changes
    Given Alice can view change logs
    And "Acme" has been changed 12 times
    When an MCP client acting for Alice opens "Acme"
    Then the client sees 10 entries in the change log

  Scenario: The client may ask for only some fields
    When an MCP client acting for Alice opens "Acme" asking only for status
    Then the record shows only id, label, status and actions

  Scenario: The feed is only included when asked for along with fields
    Given a note "Called them" was left on "Acme"
    When an MCP client acting for Alice opens "Acme" asking only for topic and feed
    Then the record shows only id, label, topic, feed and actions
    And the client sees the topic "Billing"
    And the client sees the note "Called them" in the feed

  Scenario: Only the actions the person may run are offered
    When an MCP client acting for Alice opens "Acme"
    Then the client is offered no actions

  Scenario: People who may change the record are offered its actions
    Given Alice can change customers
    When an MCP client acting for Alice opens "Acme"
    Then the client is offered the action "Mark churned"

  Scenario: Action rules decide which actions are offered
    Given Alice can change customers
    And only superusers may run "Mark churned" on customers
    When an MCP client acting for Alice opens "Acme"
    Then the client is offered no actions

  Scenario: A record that does not exist is not found
    When an MCP client acting for Alice opens a customer that does not exist
    Then the client is refused with "not found"

  Scenario Outline: A malformed record ID is refused
    When an MCP client acting for Alice calls "get_record" with:
      | id | <id> |
    Then the client is refused with "<message>"

    Examples:
      | id   | message                  |
      | 1    | Invalid ID '1'           |
      | ZZZ1 | Unknown type 'ZZZ'       |
