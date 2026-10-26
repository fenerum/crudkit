@field:CrudKitPositiveIntegerField
Feature: Links to any kind of record
  Some records, like reminders, can be about a record of any type. The link
  is shown and written as that record's ID, so it always says which type of
  record it points at, and nobody can link to a record they cannot see.

  Background:
    Given Alice can view and add reminders
    And Alice can view customers
    And a customer "Acme"
    And a reminder "Call back" with target "Acme"

  Scenario: A reminder shows the ID of the record it is about
    When Alice looks at "Call back"
    Then the target is shown with the ID of "Acme"
    And the related object id is shown with the ID of "Acme"

  Scenario Outline: Reminders about a record can be found by its ID or its number
    Given a customer "Globex"
    And a reminder "Call Globex" with target "Globex"
    When the reminders pointing at the <how> of "Acme" are looked up
    Then the lookup finds "Call back"

    Examples:
      | how    |
      | ID     |
      | number |

  Scenario: A reminder is linked to a record by its ID
    Given a customer "Globex"
    When Alice creates a reminder "Call Globex" with:
      | target | Globex |
    Then it succeeds
    And the target is shown with the ID of "Globex"

  Scenario: A reminder cannot be linked to a record the person may not see
    Given a topic "Billing"
    When Alice creates a reminder "Read up" with:
      | target | Billing |
    Then it is rejected with "not found"
    And no reminder "Read up" exists

  Scenario Outline: A reminder cannot be linked to something that is not a record ID
    When Alice creates a reminder "Read up" with the target written as "<target>"
    Then it is rejected with "<message>"

    Examples:
      | target | message                      |
      | acme   | Invalid CrudKit ID: 'acme'   |
      | CUS    | Invalid CrudKit ID: 'CUS'    |
      | XYZ1   | Model XYZ not found          |
      | CUS999 | CUS999 not found             |
