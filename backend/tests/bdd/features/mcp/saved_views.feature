@mcp-tool:list_records @mcp-tool:aggregate_records
Feature: An MCP client works from a saved view
  People can point their AI tool at a saved view ("my churned customers") and
  get the same rows, ordering and columns as in the app. The client can narrow
  a view further but never sees a view the person could not open.

  Background:
    Given Alice can view customers
    And Alice can view views
    And a customer "Acme" with status "active"
    And a customer "Beta" with status "churned"
    And a customer "Cyan" with status "churned"
    And Alice saved a view "Churned" of customers with:
      | fields   | name, status     |
      | filter   | status = churned |
      | order by | -name            |

  Scenario: Listing a view gives its rows, in its order, with its columns
    When an MCP client acting for Alice lists the view "Churned"
    Then the client sees "Cyan" and "Beta" in that order
    And each record shows only id, label, name and status

  Scenario Outline: A view can be narrowed and re-sorted
    When an MCP client acting for Alice calls "list_records" with:
      | view       | Churned |
      | <argument> | <value> |
    Then the client sees <seen> in that order

    Examples:
      | argument | value | seen              |
      | query    | beta  | "Beta"            |
      | name     | cyan  | "Cyan"            |
      | order_by | name  | "Beta" and "Cyan" |
      | type     | customers | "Cyan" and "Beta" |

  Scenario: Columns asked for replace the view's columns
    When an MCP client acting for Alice calls "list_records" with:
      | view   | Churned |
      | fields | balance |
    Then each record shows only id, label and balance

  Scenario: A view with "the person looking" shows that person's records
    Given the owner of "Acme" is "Alice"
    And Alice saved a view "Mine" of customers with:
      | filter | owner = ${user} |
    When an MCP client acting for Alice lists the view "Mine"
    Then the client sees "Acme"

  Scenario: Counting over a view
    When an MCP client acting for Alice calls "aggregate_records" with:
      | view | Churned |
    Then the client gets the groups:
      | count |
      | 2     |

  Scenario: A view is of one record type only
    When an MCP client acting for Alice calls "list_records" with:
      | view | Churned |
      | type | topics  |
    Then the client is refused with "is a view of CUS, not TOP"

  Scenario: Someone else's private view is not found
    Given Bob can view customers
    And Bob can view views
    And Bob saved a private view "Bob's list" of customers
    When an MCP client acting for Alice lists the view "Bob's list"
    Then the client is refused with "not found"

  Scenario: A person's own private view can be listed
    Given Alice saved a private view "My list" of customers
    When an MCP client acting for Alice lists the view "My list"
    Then the client is told there are 3 in total

  Scenario: Without permission to see saved views, no view is found
    Given Carol can view customers
    When an MCP client acting for Carol lists the view "Churned"
    Then the client is refused with "not found"

  Scenario: A view of a type the person may not view is refused
    Given Dave can view views
    When an MCP client acting for Dave lists the view "Churned"
    Then the client is refused with "Permission denied"

  Scenario: A deleted view is not found
    Given the view "Churned" was deleted
    When an MCP client acting for Alice lists the view "Churned"
    Then the client is refused with "not found"

  Scenario: Something that is not a view is refused
    When an MCP client acting for Alice calls "list_records" with:
      | view | Acme |
    Then the client is refused with "Invalid view ID"
