@mcp-tool:describe_types
Feature: An MCP client learns what it can work with
  Before reading or writing, an MCP client asks which record types exist and,
  for one type, how to filter it, which fields it may write, which actions it
  may run and which saved views it may open. Everything it is told is
  trimmed to what the person behind the client may do.

  Background:
    Given Alice can view customers
    And Alice can view topics

  Scenario: The client is told the record types the person may view
    When an MCP client acting for Alice asks which record types there are
    Then the client is offered the record types "agent", "topic" and "customer"

  Scenario: The client learns how to filter a type
    When an MCP client acting for Alice describes customers
    Then the client learns that "status" is one of "active" and "churned"
    And the client may filter on "name", "status", "topic", "topic_isnull", "balance_from", "balance_to" and "created_at_from"
    And the client may not filter on "id"
    And the client is told the type can be searched

  Scenario: The client learns which fields it may write and read
    When an MCP client acting for Alice describes customers
    Then the client may write "name", "email", "status", "topic", "owner" and "balance"
    And the client may not write "id", "created_by", "updated_at" and "deleted"
    And the client must give "name" when creating
    And the client may ask for the columns "name", "created_at" and "balance"
    And the client may total "balance"

  Scenario: Without permission to change, no writing and no actions are described
    When an MCP client acting for Alice describes customers
    Then the client is told it may neither create nor update them
    And the client is offered no actions

  Scenario: With permission to add and change, writing and actions are described
    Given Alice can add and change customers
    When an MCP client acting for Alice describes customers
    Then the client is told it may create and update them
    And the client is offered the action "Mark churned"

  Scenario: The client is told which changes need a person's approval
    Given Alice can change customers
    And changes to the status of customers need a person's approval
    And running "Mark churned" needs approval
    When an MCP client acting for Alice describes customers
    Then the client is told changes to "status" need approval
    And the client is offered the action "Mark churned", which needs approval

  Scenario: The client is offered the saved views of the type that the person may open
    Given Alice can view views
    And Bob can view customers
    And Alice saved a view "Churned" of customers
    And Alice saved a view "Big topics" of topics
    And Bob saved a private view "Bob's list" of customers
    When an MCP client acting for Alice describes customers
    Then the client is offered the saved views "Churned"

  Scenario: Type names are in English whatever language the server speaks
    When an MCP client acting for Alice describes customers to a Danish-speaking server
    Then the client is told the type is called "customer", or "customers" for several

  Scenario: Describing an unknown record type is refused
    When an MCP client acting for Alice calls "describe_types" with:
      | type | ZZZ |
    Then the client is refused with "Unknown type 'ZZZ'"

  Scenario: Describing a record type the person may not view is refused
    When an MCP client acting for Alice describes tickets
    Then the client is refused with "Permission denied"
