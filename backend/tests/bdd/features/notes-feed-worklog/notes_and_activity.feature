@type:FEI
Feature: Notes and the activity on a record
  Every record has an activity feed where people and the assistant leave
  notes, so the story of a customer is in one place. The newest entries come
  first, and removed notes disappear from it.

  Background:
    Given Alice can view customers
    And Alice can view, add and delete feed items
    And a customer "Acme"

  Scenario: A note left on a record shows up in its activity
    When Alice leaves the note "Called about the renewal" on "Acme"
    Then it succeeds
    And the activity of "Acme" is "Called about the renewal"
    And the note "Called about the renewal" is by Alice

  Scenario: The newest activity comes first
    Given a note "First call" was left on "Acme"
    And a note "Second call" was left on "Acme"
    Then the activity of "Acme" is "Second call" and "First call"

  Scenario: A deleted note disappears from the activity
    Given a note "Wrong customer" was left on "Acme"
    When Alice deletes "Wrong customer"
    Then it succeeds
    And the activity of "Acme" is empty

  Scenario: Notes can only be left on records the person can see
    Given Bob can view and add feed items
    When Bob leaves the note "Sneaky" on "Acme"
    Then it is rejected with "not found"
    And the activity of "Acme" is empty

  Scenario: The assistant can add a note on someone's behalf, and it can be undone
    When the assistant adds the note "Prefers email" to "Acme" on Alice's behalf
    Then the activity of "Acme" is "Prefers email"
    And the note "Prefers email" is by Alice
    When Alice undoes that change
    Then it succeeds
    And the activity of "Acme" is empty

  Scenario: The assistant cannot add an empty note
    When the assistant adds the note "   " to "Acme" on Alice's behalf
    Then the note is refused with "Note body is empty"
    And the activity of "Acme" is empty
