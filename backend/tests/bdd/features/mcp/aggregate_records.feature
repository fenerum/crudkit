@mcp-tool:aggregate_records
Feature: An MCP client counts and totals records
  Questions like "how many customers churned per month?" are answered by the
  server in one call instead of the client paging through every record.
  Counts, sums, averages, minimums and maximums can be grouped by up to two
  fields or by date period.

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
    And "Acme" was created on "2026-01-15"
    And "Beta" was created on "2026-03-10"
    And "Cyan" was created on "2026-03-20"

  Scenario: Counting all records of a type
    When an MCP client acting for Alice counts customers
    Then the client gets the groups:
      | count |
      | 3     |
    And the client is told there are 3 in total
    And the client is told these are all the groups

  Scenario: Counting with a filter
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type   | customers |
      | status | churned   |
    Then the client gets the groups:
      | count |
      | 2     |

  Scenario: Grouping by a field with several metrics
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers                            |
      | group_by | status                               |
      | metrics  | count, sum:balance, max:created_at   |
    Then the client gets the groups:
      | status  | count | sum_balance | max_created_at            |
      | active  | 1     | 100         | 2026-01-15T12:00:00+00:00 |
      | churned | 2     | 50          | 2026-03-20T12:00:00+00:00 |

  Scenario: Averages and minimums
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type    | customers                   |
      | metrics | avg:balance, min:created_at |
    Then the client gets the groups:
      | avg_balance | min_created_at            |
      | 75          | 2026-01-15T12:00:00+00:00 |

  Scenario: Grouping by month
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers        |
      | group_by | created_at:month |
    Then the client gets the groups:
      | created_at_month | count |
      | 2026-01-01       | 1     |
      | 2026-03-01       | 2     |

  Scenario: Grouping by day
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers      |
      | group_by | created_at:day |
    Then the client gets the groups:
      | created_at_day | count |
      | 2026-01-15     | 1     |
      | 2026-03-10     | 1     |
      | 2026-03-20     | 1     |

  Scenario Outline: Grouping by <period>
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers           |
      | group_by | created_at:<period> |
    Then the client gets the groups:
      | created_at_<period> | count |
      | 2026-01-01          | 3     |

    Examples:
      | period  |
      | quarter |
      | year    |

  Scenario: Grouping by a linked record names it
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type         | customers |
      | group_by     | topic     |
      | topic isnull | false     |
    Then the client gets the groups:
      | topic   | topic_label | count |
      | Billing | Billing     | 1     |

  Scenario: Linked records the person may not see stay unnamed
    Given Bob can view customers
    When an MCP client acting for Bob calls "aggregate_records" with:
      | type         | customers |
      | group_by     | topic     |
      | topic isnull | false     |
    Then the client gets the groups:
      | topic   | topic_label | count |
      | Billing |             | 1     |

  Scenario: Ordering and limiting the groups
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers |
      | group_by | status    |
      | order_by | -count    |
      | limit    | 1         |
    Then the client gets the groups:
      | status  | count |
      | churned | 2     |
    And the client is told there are more groups

  Scenario: Up to 100 groups are given unless the client asks for more
    Given 120 more customers
    When an MCP client acting for Alice counts customers, grouped by name
    Then the client gets 100 groups
    And the client is told there are more groups

  Scenario: No more than 500 groups are given at once
    Given 520 more customers
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers |
      | group_by | name      |
      | limit    | 1000      |
    Then the client gets 500 groups
    And the client is told there are more groups

  Scenario: Counting a type the person may not view is refused
    Given Bob is a user without any permissions
    When an MCP client acting for Bob counts customers
    Then the client is refused with "Permission denied"

  Scenario Outline: Malformed questions are refused with an explanation
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type       | customers |
      | <argument> | <value>   |
    Then the client is refused with "<message>"

    Examples:
      | argument | value                 | message                             |
      | group_by | nope                  | Cannot group by 'nope'              |
      | group_by | name:month            | Cannot group by 'name:month'        |
      | group_by | created_at:hour       | Cannot group by 'created_at:hour'   |
      | group_by | status, topic, owner  | Group by at most 2 fields           |
      | metrics  | sum:name              | Cannot sum 'name': needs a numeric field |
      | metrics  | min:name              | Cannot min 'name': needs a numeric or date field |
      | metrics  | median:balance        | Unknown metric 'median:balance'     |
      | nope     | 1                     | Unknown filter(s): ['nope']         |

  Scenario: Groups can only be ordered by a group or a metric
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | customers |
      | group_by | status    |
      | order_by | name      |
    Then the client is refused with "Cannot order by 'name'"

  Scenario: Fields holding lists cannot be grouped
    Given Alice can view tickets
    When an MCP client acting for Alice calls "aggregate_records" with:
      | type     | tickets |
      | group_by | tags    |
    Then the client is refused with "Cannot group by 'tags'"
