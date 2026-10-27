@assistant-tool:propose_create @assistant-tool:propose_revert
Feature: The assistant proposes new records and undoing changes
  The assistant can propose creating a record, or undoing an earlier change
  found in a record's history. Like every proposal, nothing happens until the
  person confirms it, and the proposal is checked up front so it would not
  fail when confirmed.

  Background:
    Given Alice can view, add and change customers
    And a customer "Acme" with status "active"
    And Alice is looking at "Acme"

  Scenario: propose_create proposes a new record and creates nothing yet
    When the assistant calls propose_create with:
      | type       | customers |
      | set name   | Globex    |
      | set status | churned   |
    Then the assistant has proposed creating a customer with:
      | name   | Globex  |
      | status | churned |
    And the proposal is labelled "Create customer"
    And the assistant is told "is awaiting user confirmation"

  Scenario Outline: propose_create refuses <what>
    When the assistant calls propose_create with:
      | type        | <type>  |
      | set <field> | <value> |
    Then the assistant is refused with "<message>"
    And the assistant has proposed nothing

    Examples:
      | what                             | type      | field  | value | message                                 |
      | a type the person may not create | topics    | name   | Sales | you may not create                      |
      | a field that does not exist      | customers | mood   | happy | Unknown or read-only field(s): ['mood'] |
      | a choice that does not exist     | customers | status | gone  | status='gone' is not a valid choice     |

  Scenario: propose_create checks the new record is complete
    When the assistant calls propose_create with:
      | type       | customers |
      | set status | churned   |
    Then the assistant is refused with "This field is required."
    And the assistant has proposed nothing

  Scenario: propose_create runs the new record's own checks
    Given Alice can view and add agents
    When the assistant calls propose_create with:
      | type             | agents              |
      | set name         | Approver            |
      | set instructions | Confirm everything. |
      | set trigger      | manual              |
      | set model type   | ASP                 |
    Then the assistant is refused with "Agents can't work on assistant proposals."
    And the assistant has proposed nothing

  Scenario: propose_revert proposes undoing a change on the record it changed
    Given Alice changed the status of "Acme" to "churned"
    When the assistant calls propose_revert with:
      | change set | that change             |
      | reasoning  | Alice asked to undo it. |
    Then the assistant has proposed undoing that change on "Acme"
    And "Acme" still has status "churned"

  Scenario Outline: propose_revert refuses <what>
    Given Alice changed the status of "Acme" to "churned"
    And Alice undid that change
    When the assistant calls propose_revert with:
      | change set | <change set> |
    Then the assistant is refused with "<message>"
    And the assistant has proposed nothing

    Examples:
      | what                         | change set                   | message                               |
      | a change that never happened | a change that never happened | Unknown change set                    |
      | a change already undone      | the undone change            | This change has already been reverted |

  Scenario: propose_revert needs permission to change the record
    Given Carol can view customers
    And Alice changed the status of "Acme" to "churned"
    And Carol is looking at "Acme"
    When the assistant calls propose_revert with:
      | change set | that change |
    Then the assistant is refused with "Acme not found, or not available for change."
    And the assistant has proposed nothing
