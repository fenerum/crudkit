@type:VIW
Feature: Who sees and changes a saved view
  A view is shared with everyone unless it is made private, but only the
  person who saved it may change or delete it. People can rely on a team
  view staying as it is, and keep personal views to themselves.

  Background:
    Given Alice can view, change and delete views
    And Bob can view, change and delete views
    And Alice saved a view "Team pipeline" of customers
    And Alice saved a private view "Alice's list" of customers
    And Bob saved a private view "Bob's list" of customers

  Scenario: Everyone sees shared views and their own private ones
    When Bob lists the saved views
    Then the saved views listed are "Bob's list" and "Team pipeline"

  Scenario: The person who saved a view can change it
    When Alice changes the name of "Team pipeline" to "Sales pipeline"
    Then it succeeds
    And "Team pipeline" has name "Sales pipeline"

  Scenario: Someone else's shared view cannot be changed
    When Bob changes the name of "Team pipeline" to "Bob's pipeline"
    Then it is not found
    And "Team pipeline" still has name "Team pipeline"

  Scenario: Someone else's shared view cannot be deleted
    When Bob deletes "Team pipeline"
    Then it is not found
    And "Team pipeline" is not deleted

  Scenario: The person who saved a view can delete it
    When Alice deletes "Alice's list"
    Then it succeeds
    And "Alice's list" is deleted
