Feature: Fields that depend on other fields
  A form only asks for what fits the record as it is being filled in: a
  reading's finished date appears once the reading is marked finished, and
  goes away again if it is not.

  Background:
    Given Alice is signed in

  Scenario: The finished date appears once a new reading is finished
    Given Alice is filling in a new reading
    Then the form does not ask for the finished on
    When she picks "Finished" as the status
    Then the form asks for the finished on
    When she picks "Reading" as the status
    Then the form does not ask for the finished on

  Scenario: A finished reading's page shows its finished date, others leave it out
    Given a reading "Done" with status "Finished"
    And a reading "Later" with status "To read"
    When Alice opens "Done"
    Then she sees "Finished On"
    When Alice opens "Later"
    Then she does not see "Finished On"
