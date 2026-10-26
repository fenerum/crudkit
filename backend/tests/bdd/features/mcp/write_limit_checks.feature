Feature: The MCP write limit is checked when the server starts
  A typo in the write limit would otherwise only show up on the first MCP
  write, and a limit counted in a per-process cache silently allows every
  worker the full rate. The startup checks tell the operator about both.

  @check:crudkit_mcp.E001
  Scenario: An unreadable write limit is an error
    Given the MCP write limit is "10/fortnight"
    When the MCP system checks run
    Then the checks report the error "crudkit_mcp.E001"

  @check:crudkit_mcp.W001
  Scenario: A write limit counted per process is a warning when writing is allowed
    Given the server lets MCP clients write directly
    And the MCP write limit is "60/min"
    And the server's cache is local to each process
    When the MCP system checks run
    Then the checks report the warning "crudkit_mcp.W001"

  Scenario: A per-process cache does not matter when MCP clients cannot write
    Given the MCP write limit is "60/min"
    And the server's cache is local to each process
    When the MCP system checks run
    Then the checks report nothing about MCP

  Scenario: Without a write limit there is nothing to warn about
    Given the server lets MCP clients write directly
    And there is no MCP write limit
    And the server's cache is local to each process
    When the MCP system checks run
    Then the checks report nothing about MCP
