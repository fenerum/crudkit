@check:crudkit.E003
Feature: Calls, meetings and emails in a record's activity
  Besides notes, a project can let people add its own kinds of entries to a
  record's activity, such as a logged call or a sent email, so everything that
  happened with a customer stays in one place.

  Background:
    Given Alice can view customers
    And Alice can view and add calls
    And a customer "Acme"

  Scenario: A customer's activity offers calls to people who may add them
    When Alice looks up the description of customers
    Then the description offers adding calls to the activity

  Scenario: Calls are not offered to people who may not add them
    Given Bob can view customers
    When Bob looks up the description of customers
    Then the description does not offer adding calls to the activity

  Scenario: Calls are only offered on the record types they are meant for
    Given Alice can view tickets
    When Alice looks up the description of tickets
    Then the description does not offer adding calls to the activity

  Scenario: A kind of entry tells how it shows in the activity
    When Alice looks up the description of calls
    Then the description shows them in the activity with:
      | icon        | phone             |
      | words       | logged a call     |
      | fields      | subject and notes |
      | then runs   | Send summary      |
      | replies     | yes               |
      | attachments | call recordings   |

  Scenario: A call logged from a customer's activity shows up in it
    When Alice logs the call "Renewal chat" on "Acme"
    Then it succeeds
    And the activity of "Acme" shows the call "Renewal chat"
    And "Renewal chat" was added to the activity by Alice

  Scenario: Undoing a logged call takes it out of the activity
    Given Alice can delete calls
    When Alice logs the call "Wrong customer" on "Acme"
    And Alice undoes that change
    Then it succeeds
    And the activity of "Acme" is empty

  Scenario: Calls can only be logged on records the person can see
    Given Bob can view and add calls
    When Bob logs the call "Sneaky" on "Acme"
    Then it is rejected with "not found"
    And no call "Sneaky" was made
    And the activity of "Acme" is empty

  Scenario: Calls cannot be logged on a record type they are not meant for
    Given Alice can view tickets
    And a ticket "Printer broken"
    When Alice logs the call "Wrong place" on "Printer broken"
    Then it is rejected with "Calls can't be added to the activity of tickets"
    And no call "Wrong place" was made

  Scenario: A reply can only be started to an entry the person can see
    Given a call "Private chat" was logged on "Acme"
    And Bob can add calls
    When Bob starts a reply to "Private chat"
    Then it is rejected with "not found"

  Scenario Outline: A kind of entry declared wrongly is reported before the project starts
    Given calls declare their activity entry <mistake>
    When the record types are checked
    Then the record type check fails with "crudkit.E003" saying "<problem>"

    Examples:
      | mistake                                | problem                                  |
      | with the field "colour"                | names unknown fields: colour             |
      | without fields                         | lists no fields                          |
      | with the action "fly"                  | names 'fly', which is not an action      |
      | for records with the letters "XYZ"     | goes on unknown record types: XYZ        |
      | with attachments kept as topics        | need a foreign key to the model and a file field |
