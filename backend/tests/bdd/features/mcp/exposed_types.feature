@mcp-tool:describe_types @mcp-tool:list_records
Feature: Which record types MCP clients can reach
  MCP clients see the project's own record types, never Django's users or
  CrudKit's internal bookkeeping, apart from the AI context documents and
  agents that people manage with AI help. A project can hide a type, or allow
  only a short list of types, without affecting the in-app assistant and
  agents.

  Scenario: The project's types are exposed, with AI context and agents
    Given Alice is a superuser
    When an MCP client acting for Alice asks which record types there are
    Then the client is offered the record types "AI context", "agent", "topic", "customer", "ticket", "comment", "reminder" and "urgent comment"

  Scenario: A project can hide a type from MCP clients
    Given Alice can view customers
    And Alice can view topics
    And customers are hidden from MCP clients
    When an MCP client acting for Alice lists customers
    Then the client is refused with "Unknown type 'CUS'"

  Scenario: A project can allow only some types
    Given Alice is a superuser
    And MCP clients may only use customers
    When an MCP client acting for Alice asks which record types there are
    Then the client is offered the record types "customer"
    And an agent may still be set up to work on tickets

  Scenario: Fields filled in by AI or by CrudKit itself are not writable
    Given Alice can view tickets
    When an MCP client acting for Alice describes tickets
    Then the client may write "subject", "body" and "customer"
    And the client may not write "summary", "is_urgent", "tags", "topic", "created_by", "updated_at", "id", "deleted" and "merged_into"

  Scenario: The parts of a link to any record are not writable
    Given Alice can view reminders
    When an MCP client acting for Alice describes reminders
    Then the client may write "note"
    And the client may not write "related_content_type" and "related_object_id"
