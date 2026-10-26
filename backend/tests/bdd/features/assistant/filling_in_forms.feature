@assistant-tool:fill_form @assistant-tool:open_create_form
Feature: The assistant fills in forms in the person's browser
  In the chat, the assistant can fill in the form a person has open, or open
  a new one already filled in. Nothing is saved: the person reviews the form
  and saves it themselves, so the form tools only fill in what that person
  could save.

  Background:
    Given Alice can view, add and change customers
    And Alice can view topics
    And a topic "Billing"
    And a customer "Acme"

  Scenario: fill_form fills in the open create form and saves nothing
    Given Alice has a new customer form open
    When the assistant calls fill_form with:
      | set name   | Globex  |
      | set status | churned |
      | set topic  | Billing |
    Then the form on the screen is filled in with:
      | name   | Globex  |
      | status | churned |
      | topic  | Billing |
    And the assistant is told "Filled name, status, topic in the customer form on the user's screen."
    And the assistant is told "the user reviews the form and clicks Create."
    And the assistant has proposed nothing

  Scenario: fill_form fills in the edit form of a record the person may change
    Given Alice has the edit form of "Acme" open
    When the assistant calls fill_form with:
      | set name | Acme Inc |
    Then the form on the screen is filled in with:
      | name | Acme Inc |
    And the assistant is told "clicks Save."
    And "Acme" still has name "Acme"

  Scenario: fill_form needs an open form
    Given Alice is looking at "Acme"
    When the assistant calls fill_form with:
      | set name | Globex |
    Then the assistant is refused with "No form is open. Use open_create_form to start a new record."
    And no form is touched

  Scenario Outline: fill_form refuses <what>
    Given Alice has a new customer form open
    When the assistant calls fill_form with:
      | set <field> | <value> |
    Then the assistant is refused with "<message>"
    And no form is touched

    Examples:
      | what                           | field      | value     | message                                       |
      | a field that does not exist    | mood       | happy     | Unknown or read-only field(s): ['mood']       |
      | a field that cannot be written | created by | Alice     | Unknown or read-only field(s): ['created_by'] |
      | a choice that does not exist   | status     | gone      | status='gone' is not a valid choice           |
      | a record that does not exist   | topic      | TOP999999 | topic: topic 'TOP999999' not found            |

  Scenario: fill_form on a new record needs permission to create one
    Given Carol can view customers
    And Carol has a new customer form open
    When the assistant calls fill_form with:
      | set name | Globex |
    Then the assistant is refused with "you may not create"
    And no form is touched

  Scenario: fill_form on an edit form needs permission to change the record
    Given Carol can view customers
    And Carol has the edit form of "Acme" open
    When the assistant calls fill_form with:
      | set name | Acme Inc |
    Then the assistant is refused with "Acme not found, or not available for change."
    And no form is touched

  Scenario: open_create_form opens a new form, filled in
    Given Alice is looking at "Acme"
    When the assistant calls open_create_form with:
      | type      | customers |
      | set name  | Globex    |
      | set topic | Billing   |
    Then a new customer form opens filled in with:
      | name  | Globex  |
      | topic | Billing |
    And the assistant is told "clicks Create."
    And the assistant has proposed nothing

  Scenario: open_create_form can open an empty form
    Given Alice is looking at "Acme"
    When the assistant calls open_create_form with:
      | type | customers |
    Then an empty customer form opens
    And the assistant is told "Opened a new customer form. Nothing is created until the user clicks Create."

  Scenario Outline: open_create_form refuses <what>
    Given Alice is looking at "Acme"
    When the assistant calls open_create_form with:
      | type        | <type>  |
      | set <field> | <value> |
    Then the assistant is refused with "<message>"
    And no form is touched

    Examples:
      | what                             | type       | field  | value  | message                             |
      | a type the person may not create | topics     | name   | Sales  | you may not create                  |
      | a type that does not exist       | spaceships | name   | Apollo | Unknown type 'spaceships'           |
      | a choice that does not exist     | customers  | status | gone   | status='gone' is not a valid choice |
