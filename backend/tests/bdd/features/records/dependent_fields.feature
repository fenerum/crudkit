@check:crudkit.E004
Feature: Fields that depend on other fields
  Some fields only make sense in certain situations: a reason for losing a
  deal, special terms when a deal has them, a product that fits the chosen
  category, a ticket of the deal's own customer. A record type declares how
  its fields depend on each other, the app's forms follow along as people
  type, and every way of saving a record keeps to the same rules.

  Background:
    Given Alice can view, add and change deals
    And Alice can view customers
    And Alice can view tickets
    And a deal "Big deal" with stage "open"

  Scenario: A field required in one situation must be filled in when the record gets there
    When Alice changes the stage of "Big deal" to "lost"
    Then it is rejected with "Lost reason is required when stage is Lost."
    And "Big deal" still has stage "open"

  Scenario: Filling in the field while moving into the situation succeeds
    When Alice changes "Big deal" with:
      | stage       | lost             |
      | lost reason | Went with Globex |
    Then it succeeds
    And "Big deal" has stage "lost"
    And "Big deal" has lost reason "Went with Globex"

  Scenario: A new record is held to the same rules
    When Alice creates a deal "Small deal" with:
      | stage | lost |
    Then it is rejected with "Lost reason is required when stage is Lost."

  Scenario: A field that stops applying is cleared, so it never shows a stale value
    Given a deal "Lost deal" with:
      | stage       | lost             |
      | lost reason | Went with Globex |
    When Alice changes the stage of "Lost deal" to "open"
    Then it succeeds
    And "Lost deal" has lost reason ""

  Scenario: Undoing the change brings the cleared value back
    Given a deal "Lost deal" with:
      | stage       | lost             |
      | lost reason | Went with Globex |
    And Alice changed the stage of "Lost deal" to "open"
    When Alice undoes that change
    Then it succeeds
    And "Lost deal" has stage "lost"
    And "Lost deal" has lost reason "Went with Globex"

  Scenario: A value for a field that does not apply is not kept
    When Alice changes the special terms of "Big deal" to "Net 90"
    Then it succeeds
    And "Big deal" has special terms ""

  Scenario: A yes/no field can make another field apply
    When Alice changes "Big deal" with:
      | has special terms | true   |
      | special terms     | Net 90 |
    Then it succeeds
    And "Big deal" has special terms "Net 90"

  Scenario: Choices narrow to those that fit another field
    Given the category of "Big deal" is "hardware"
    When Alice changes the product of "Big deal" to "saas"
    Then it is rejected with "Saas is not allowed when category is Hardware."
    And "Big deal" still has product ""

  Scenario: A choice that fits the other field is accepted
    Given the category of "Big deal" is "hardware"
    When Alice changes the product of "Big deal" to "laptop"
    Then it succeeds
    And "Big deal" has product "laptop"

  Scenario: Every choice is open while the other field is empty
    When Alice changes the product of "Big deal" to "saas"
    Then it succeeds

  Scenario: A linked record must share the record's own customer
    Given a customer "Acme"
    And a customer "Globex"
    And a ticket "Printer broken" with customer "Globex"
    And the customer of "Big deal" is "Acme"
    When Alice changes the ticket of "Big deal" to "Printer broken"
    Then it is rejected with "does not belong to the customer of this deal"
    And "Big deal" still has ticket ""

  Scenario: A linked record of the same customer is accepted
    Given a customer "Acme"
    And a ticket "Printer broken" with customer "Acme"
    And the customer of "Big deal" is "Acme"
    When Alice changes the ticket of "Big deal" to "Printer broken"
    Then it succeeds
    And "Big deal" has ticket "Printer broken"

  Scenario: Changing many records at once skips those that would break the rules
    Given a deal "Lost deal" with:
      | stage       | lost             |
      | lost reason | Went with Globex |
    When Alice sets the stage of "Big deal" and "Lost deal" to "lost" at once
    Then 1 record was changed
    And "Big deal" was skipped because "Lost reason is required when stage is Lost."

  Scenario: An MCP client is held to the same rules
    Given the server lets MCP clients write directly
    And Alice connected the MCP client "Research Bot" with write access
    When an MCP client acting for Alice changes the stage of "Big deal" to "lost"
    Then the client is refused with "Lost reason is required when stage is Lost."
    And "Big deal" still has stage "open"

  Scenario: An MCP client learns how fields depend on each other
    When an MCP client acting for Alice describes deals
    Then the client learns that "lost_reason" applies only when "stage" is "lost"
    And the client learns that "lost_reason" is required while it applies

  Scenario: The description tells forms how fields depend on each other
    When Alice looks up the description of deals
    Then the field "lost reason" applies only when stage is "lost"
    And the field "lost reason" is required while it applies
    And the field "special terms" applies only when has special terms is "true"
    And the field "product" offers "laptop" and "phone" when category is "hardware"
    And the field "ticket" only offers tickets that share the customer
    And the field "stage" depends on no other field

  Scenario Outline: A dependency declared wrongly is reported before the project starts
    Given <declaration>
    When the record types are checked
    Then the record type check fails with "crudkit.E004" saying "<problem>"

    Examples:
      | declaration                                                                   | problem                                   |
      | deals declare the field "lost reason" as depending on the colour              | depends on the unknown field 'colour'     |
      | deals declare the field "colour" as applying only when the stage is "lost"    | names the unknown field 'colour'          |
      | deals declare the field "name" as applying only when the stage is "lost"      | must allow blank                          |
      | deals declare the field "category" as applying only when the category is "x" | depends on itself                         |
      | deals declare the field "name" as matching the customer of the record it links to | is not a foreign key                  |
