Feature: Search a list
  Every list has a search field. It matches part of the fields the record
  type is searched by, or a record's exact ID, so a pasted ID always finds
  its record.

  Background:
    Given Alice can view customers
    And Alice can view comments
    And a customer "Acme Corp" with email "hello@acme.test"
    And a customer "Globex" with email "billing@globex.test"

  Scenario Outline: A list search matches part of any searched field, ignoring case
    When Alice searches the customers for "<query>"
    Then the list holds only "<found>"

    Examples:
      | query       | found     |
      | acme        | Acme Corp |
      | GLOBEX.TEST | Globex    |

  Scenario: A list search finds a record by its exact ID, however it is typed
    When Alice looks for the ID of "Acme Corp" in lower case, padded with spaces, in the list of customers
    Then the list holds only "Acme Corp"

  Scenario: Another type's ID finds nothing in a list
    Given a ticket "Outage"
    When Alice looks for the ID of "Outage" in the list of customers
    Then the list holds nothing

  Scenario: A record type without searched fields can only be searched by ID
    Given a ticket "Outage"
    And a comment "Looking into it" with ticket "Outage"
    When Alice searches the comments for "Looking"
    Then the list holds nothing

  Scenario: A record type without searched fields can still be searched by ID
    Given a ticket "Outage"
    And a comment "Looking into it" with ticket "Outage"
    When Alice looks for the ID of "Looking into it" in the list of comments
    Then the list holds only "Looking into it"

  Scenario: A record of an extending type is found by its own ID in the list it extends
    Given a ticket "Outage"
    And an urgent comment "Server down" on the ticket "Outage"
    When Alice looks for the ID of "Server down" in the list of comments
    Then the list holds only "Server down"
