@assistant-tool:propose_patch @assistant-tool:propose_bulk_patch @assistant-tool:propose_action @assistant-tool:propose_create_note
Feature: The assistant proposes changes to records
  The assistant cannot change anything by itself. What it would change is
  filed as a proposal and shown to the person as a card to confirm or skip,
  and it may only propose what that person could do themselves, with values
  that would actually be accepted.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And Alice is looking at "Acme"

  Scenario: propose_patch proposes a change to the record on screen and changes nothing yet
    When the assistant calls propose_patch with:
      | set status | churned                    |
      | reasoning  | They cancelled their plan. |
    Then the assistant has proposed changing the status of "Acme" to "churned"
    And the assistant is told "is awaiting user confirmation. The action has NOT run yet."
    And "Acme" still has status "active"

  Scenario: propose_patch can propose a change to another record
    Given a customer "Beta"
    When the assistant calls propose_patch with:
      | record   | Beta     |
      | set name | Beta Inc |
    Then the assistant has proposed changing the name of "Beta" to "Beta Inc"

  Scenario: propose_patch can point a foreign key at a record the person may see
    Given Alice can view topics
    And a topic "Billing"
    When the assistant calls propose_patch with:
      | set topic | Billing |
    Then the assistant has proposed changing the topic of "Acme" to "Billing"

  Scenario Outline: propose_patch refuses <what>
    Given a topic "Secret"
    When the assistant calls propose_patch with:
      | set <field> | <value> |
    Then the assistant is refused with "<message>"
    And the assistant has proposed nothing

    Examples:
      | what                            | field      | value     | message                                                           |
      | a field that does not exist     | mood       | happy     | Unknown or read-only field(s): ['mood']                           |
      | a field that cannot be written  | created by | Alice     | Unknown or read-only field(s): ['created_by']                     |
      | a choice that does not exist    | status     | gone      | status='gone' is not a valid choice; valid: ['active', 'churned'] |
      | a record the person may not see | topic      | Secret    | topic: topic 'Secret' not found                                   |
      | a record that does not exist    | topic      | TOP999999 | topic: topic 'TOP999999' not found                                |

  Scenario: propose_patch refuses a record the person may not change
    Given Carol can view customers
    And Carol is looking at "Acme"
    When the assistant calls propose_patch with:
      | set status | churned |
    Then the assistant is refused with "Acme not found, or not available for change."
    And the assistant has proposed nothing

  Scenario: The assistant may not propose changes to CrudKit's own bookkeeping
    Given Alice can view and change assistant proposals
    And the assistant has proposed changing the status of "Acme" to "churned"
    When the assistant calls propose_action with:
      | record      | the proposal |
      | action name | confirm      |
    Then the assistant is refused with "the proposal can't be changed by the assistant."

  Scenario: During a dry run the assistant's proposals are reported but not filed
    Given the assistant is making a dry run
    When the assistant calls propose_patch with:
      | set status | churned |
    Then the assistant would have proposed changing the status of "Acme" to "churned"
    And the assistant is told "Dry run"
    And the assistant is told "nothing was saved."

  Scenario: propose_bulk_patch proposes the same change on several records, one card each
    Given a customer "Beta" with status "active"
    When the assistant calls propose_bulk_patch with:
      | records    | Acme and Beta   |
      | set status | churned         |
      | reasoning  | Both cancelled. |
    Then the assistant has made 2 proposals
    And the assistant has proposed changing the status of "Acme" to "churned"
    And the assistant has proposed changing the status of "Beta" to "churned"
    And "Acme" still has status "active"

  Scenario: propose_bulk_patch leaves out records that already have the values
    Given a customer "Beta" with status "churned"
    When the assistant calls propose_bulk_patch with:
      | records    | Acme and Beta |
      | set status | churned       |
    Then the assistant has made 1 proposals
    And the assistant has proposed changing the status of "Acme" to "churned"
    And the assistant is told "Already set, not proposed: Beta."

  Scenario: propose_bulk_patch proposes each record once
    When the assistant calls propose_bulk_patch with:
      | records    | Acme, Acme and Acme |
      | set status | churned             |
    Then the assistant has made 1 proposals

  Scenario: propose_bulk_patch reports the records it may not change and proposes the rest
    Given people may only change the customers they are the owner of
    And a customer "Beta" with owner "Alice"
    When the assistant calls propose_bulk_patch with:
      | records    | Acme, Beta and nonsense |
      | set status | churned                 |
    Then the assistant has made 1 proposals
    And the assistant has proposed changing the status of "Beta" to "churned"
    And the assistant is told "Not proposed: Acme not found, or not available for change."
    And the assistant is told "Invalid id 'nonsense'"

  Scenario: propose_bulk_patch proposes nothing when every record is refused
    Given Carol can view customers
    And Carol is looking at "Acme"
    When the assistant calls propose_bulk_patch with:
      | records    | Acme    |
      | set status | churned |
    Then the assistant is refused with "no proposals made."
    And the assistant has proposed nothing

  Scenario: propose_bulk_patch refuses a value that would be refused on any of the records
    Given a customer "Beta"
    When the assistant calls propose_bulk_patch with:
      | records    | Acme and Beta |
      | set status | gone          |
    Then the assistant is refused with "status='gone' is not a valid choice"
    And the assistant has proposed nothing

  Scenario: propose_bulk_patch takes at most 100 records at a time
    Given there are 101 customers to choose from
    When the assistant calls propose_bulk_patch on every customer, setting status to "churned"
    Then the assistant is refused with "at most 100 ids per call; split the records into batches."
    And the assistant has proposed nothing

  Scenario: propose_action proposes running an action on the record
    When the assistant calls propose_action with:
      | action name | mark_churned         |
      | reasoning   | They stopped paying. |
    Then the assistant has proposed running "mark_churned" on "Acme"
    And the proposal is labelled "Run mark_churned"
    And "Acme" still has status "active"

  Scenario: propose_action refuses an action that does not exist and names the ones that do
    When the assistant calls propose_action with:
      | action name | delete_everything |
    Then the assistant is refused with "action 'delete_everything' does not exist on this object. Valid actions: ['mark_churned']"
    And the assistant has proposed nothing

  Scenario: propose_action only offers actions the person may run
    Given only superusers may run "Mark churned" on customers
    When the assistant calls propose_action with:
      | action name | mark_churned |
    Then the assistant is refused with "Valid actions: []"
    And the assistant has proposed nothing

  Scenario: propose_create_note proposes a note labelled with its first line
    When the assistant calls propose_create_note with:
      | body | Customer asked for a callback on Monday |
    Then the assistant has proposed adding the note "Customer asked for a callback on Monday" to "Acme"
    And the proposal is labelled "Add note: Customer asked for a callback on Monday"
