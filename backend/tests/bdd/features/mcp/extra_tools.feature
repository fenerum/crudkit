@endpoint:crudkit_mcp
Feature: A project adds its own MCP tools
  Projects can give MCP clients extra tools, or replace a built-in one with
  their own. An extra tool that writes is only offered to clients with write
  access, since it does not go through the proposal Inbox.

  Background:
    Given Alice can view customers

  Scenario: An extra tool is offered and can be called
    Given the project adds the MCP tool "crm_status"
    When an MCP client acting for Alice asks which tools it may use
    Then the client is offered the tool "crm_status"
    When an MCP client acting for Alice calls "crm_status"
    Then the client is told "all good"

  Scenario: A project can replace a built-in tool
    Given the project replaces the MCP tool "list_records"
    When an MCP client acting for Alice calls "list_records"
    Then the client is told "the project's own listing"

  Scenario: An extra write tool is not offered to a client that may only propose
    Given the project adds the MCP write tool "sync_now"
    And Alice connected an MCP client with propose access
    When an MCP client acting for Alice asks which tools it may use
    Then the client is not offered the tool "sync_now"

  Scenario: An extra write tool is offered to a client that may write
    Given the server lets MCP clients write directly
    And the project adds the MCP write tool "sync_now"
    And Alice connected an MCP client with write access
    When an MCP client acting for Alice asks which tools it may use
    Then the client is offered the tool "sync_now"
