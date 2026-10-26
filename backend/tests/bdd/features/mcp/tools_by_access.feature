@endpoint:crudkit_mcp
Feature: The tools an MCP client is offered
  The tool set is the same in every CrudKit project, so one client works
  everywhere. Reading tools are always there; the writing tools appear when
  the person granted propose access (the changes wait for them in their Inbox)
  or write access on a server that allows writing directly.

  Background:
    Given Alice can view customers

  Scenario: A client with read access is offered only the reading tools
    Given Alice connected an MCP client with read access
    When an MCP client acting for Alice asks which tools it may use
    Then the client is offered the tools "describe_types", "search", "list_records", "aggregate_records" and "get_record"
    And every tool is marked as read-only

  Scenario: Write access does nothing on a server that does not allow writing
    Given Alice connected an MCP client with write access
    When an MCP client acting for Alice asks which tools it may use
    Then the client is offered the tools "describe_types", "search", "list_records", "aggregate_records" and "get_record"

  Scenario Outline: Writing tools are offered with <access> access
    Given the server lets MCP clients write directly
    And Alice connected an MCP client with <access> access
    When an MCP client acting for Alice asks which tools it may use
    Then the client is offered the tools "describe_types", "search", "list_records", "aggregate_records", "get_record", "create_record", "update_record", "run_action", "add_note" and "undo"
    And every write tool is marked as changing data

    Examples:
      | access  |
      | write   |
      | propose |

  Scenario: Proposing needs the assistant app, which keeps the Inbox
    Given the assistant app is not installed
    And Alice connected an MCP client with propose access
    When an MCP client acting for Alice asks which tools it may use
    Then the client is offered the tools "describe_types", "search", "list_records", "aggregate_records" and "get_record"

  Scenario: The tools only accept the record types the person may view
    When an MCP client acting for Alice asks which tools it may use
    Then the tools accept the record types "customer" and "agent"
