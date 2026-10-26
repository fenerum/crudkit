@mcp-tool:list_records
Feature: An MCP client lists records
  The list tool pages through one record type, narrowed by filters (the keys
  describe_types reports), a free-text search, an ordering and the columns
  the client asks for. Deleted records and records the person may not see are
  never listed.

  Background:
    Given Alice can view customers
    And Alice can view topics
    And a topic "Billing"
    And a customer "Acme" with:
      | status  | active  |
      | topic   | Billing |
      | balance | 100     |
    And a customer "Beta" with:
      | status  | churned |
      | balance | 50      |
    And a customer "Cyan" with status "churned"

  Scenario: Listing gives the records that are not deleted, with a total
    Given Alice can delete customers
    And a customer "Gone"
    And Alice deleted "Gone"
    When an MCP client acting for Alice lists customers
    Then the client sees "Acme", "Beta" and "Cyan"
    And the client is told there are 3 in total

  Scenario Outline: Filtering on <filter>
    When an MCP client acting for Alice lists customers with <filter> "<value>"
    Then the client sees <seen>

    Examples:
      | filter       | value             | seen                       |
      | name         | ACM               | "Acme"                     |
      | status       | churned           | "Beta" and "Cyan"          |
      | topic        | Billing           | "Acme"                     |
      | status       | active or churned | "Acme", "Beta" and "Cyan"  |
      | topic        | Billing or Billing | "Acme"                    |
      | balance from | 60                | "Acme"                     |
      | balance to   | 60                | "Beta"                     |
      | topic isnull | true              | "Beta" and "Cyan"          |
      | topic isnull | false             | "Acme"                     |

  Scenario Outline: Filtering on a date range
    Given "Acme" was created on "2026-01-15"
    And "Beta" was created on "2026-03-10"
    And "Cyan" was created on "2026-05-20"
    When an MCP client acting for Alice lists customers with <filter> "<value>"
    Then the client sees <seen>

    Examples:
      | filter          | value      | seen              |
      | created at from | 2026-03-01 | "Beta" and "Cyan" |
      | created at to   | 2026-03-31 | "Acme" and "Beta" |

  Scenario: Searching within a type
    When an MCP client acting for Alice lists customers matching "cy"
    Then the client sees "Cyan"

  Scenario: Sorting, skipping and limiting
    When an MCP client acting for Alice calls "list_records" with:
      | type     | customers |
      | order_by | -name     |
      | offset   | 1         |
      | limit    | 1         |
    Then the client sees "Beta"
    And the client is told there are 3 in total

  Scenario: Up to 20 records are listed unless the client asks for more
    Given 25 more customers
    When an MCP client acting for Alice lists customers
    Then the client receives 20 records
    And the client is told there are 28 in total

  Scenario: No more than 100 records are listed at once
    Given 120 more customers
    When an MCP client acting for Alice calls "list_records" with:
      | type  | customers |
      | limit | 500       |
    Then the client receives 100 records

  Scenario: The client may ask for only some columns
    When an MCP client acting for Alice calls "list_records" with:
      | type   | customers |
      | fields | status    |
    Then each record shows only id, label and status

  Scenario Outline: Malformed listings are refused
    When an MCP client acting for Alice calls "list_records" with:
      | type       | customers |
      | <argument> | <value>   |
    Then the client is refused with "<message>"

    Examples:
      | argument     | value       | message                                 |
      | nope         | 1           | Unknown filter(s): ['nope']             |
      | name         | acme or bet | Filter 'name' takes one value, not a list |
      | balance from | 1 or 2      | Filter 'balance_from' takes one value, not a list |
      | order_by     | password    | Cannot order by 'password'              |
      | fields       | nope        | Unknown field(s): ['nope']              |

  Scenario: Listing an unknown record type is refused
    When an MCP client acting for Alice calls "list_records" with:
      | type | ZZZ |
    Then the client is refused with "Unknown type 'ZZZ'"

  Scenario: Listing a type the person may not view is refused
    Given Bob is a user without any permissions
    When an MCP client acting for Bob lists customers
    Then the client is refused with "Permission denied"

  Scenario: Row rules apply to MCP clients too
    Given people may only get customers with status "active"
    When an MCP client acting for Alice lists customers
    Then the client sees "Acme"
