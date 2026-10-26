@endpoint:search-list
Feature: Search everything
  The search box looks through every record type a person may view at once,
  so they can jump to a customer, a ticket or any other record by typing part
  of its name or its ID. It shows a handful of hits per type, and more when the
  search is narrowed down to one type.

  Background:
    Given Alice can view customers
    And Alice can view tickets
    And Alice can view topics
    And a customer "Acme Corp"
    And a ticket "ACME printer jammed"
    And a topic "Acme onboarding"

  Scenario: Records of every type are found by part of their searched fields, ignoring case
    When Alice searches for "acme"
    Then the search finds "Acme Corp" and "ACME printer jammed"

  Scenario: An empty search finds nothing
    When Alice searches for ""
    Then the search finds nothing

  Scenario: Only record types the person may view are searched
    Given Bob can view tickets
    When Bob searches for "acme"
    Then the search finds "ACME printer jammed"

  Scenario: Deleted records are not found
    Given Alice can delete customers
    And Alice deleted "Acme Corp"
    When Alice searches for "acme"
    Then the search finds "ACME printer jammed"

  Scenario: Only the records the person may see are found
    Given people may view and change the customers they created without a permission
    And Carol is a user without any permissions
    And Carol owns a customer "Acme Ltd"
    When Carol searches for "acme"
    Then the search finds "Acme Ltd"

  Scenario: A record is found by its ID, typed in any case
    When Alice searches for the ID of "Acme Corp" in lower case
    Then the search finds "Acme Corp"

 
  Scenario: A record of a type that extends another is found once by its ID, as its own type
    Given Alice can view comments
    And Alice can view urgent comments
    And an urgent comment "Paper jam again" on the ticket "ACME printer jammed"
    When Alice searches for the ID of "Paper jam again"
    Then the search finds "Paper jam again"
    And the search finds 1 urgent comment

  Scenario: A search can be narrowed down to one record type
    When Alice searches only tickets for "acme"
    Then the search finds "ACME printer jammed"

  Scenario Outline: A search shows up to 6 hits per type, or 21 when narrowed down to one type
    Given 25 customers named "Acme" followed by a number
    When <search>
    Then the search finds <count> customers

    Examples:
      | search                                  | count |
      | Alice searches for "acme"               | 6     |
      | Alice searches only customers for "acme" | 21    |

  Scenario: A hit gives only what the search box shows
    When Alice searches for "acme"
    Then each search result gives only its ID, label and pictures

  Scenario: Searching needs signing in
    When someone who is not signed in searches for "acme"
    Then it requires signing in
