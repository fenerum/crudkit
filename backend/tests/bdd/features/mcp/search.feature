@mcp-tool:search
Feature: An MCP client searches across record types
  The search tool finds records of any type by text or by record ID, the way
  the search box in the app does, limited to what the person may see.

  Background:
    Given Alice can view customers
    And a customer "Acme Corp"
    And a customer "Beta"

  Scenario: Searching by text finds matching records
    When an MCP client acting for Alice searches for "acme"
    Then the client sees "Acme Corp"

  Scenario: Searching by record ID finds that record
    When an MCP client acting for Alice searches for "Beta" by its record ID
    Then the client sees "Beta"

  Scenario: An empty search is answered without searching
    When an MCP client acting for Alice searches for ""
    Then the client is told "No query provided"

  Scenario: A search without hits says so
    When an MCP client acting for Alice searches for "zzz"
    Then the client is told "No results found"

  Scenario: Records the person may not see are not found
    Given Bob is a user without any permissions
    When an MCP client acting for Bob searches for "acme"
    Then the client is told "No results found"

  Scenario: Types hidden from MCP clients are not searched
    Given customers are hidden from MCP clients
    When an MCP client acting for Alice searches for "acme"
    Then the client is told "No results found"
