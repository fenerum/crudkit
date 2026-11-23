@type:ROL @type:RLM @type:FLA @endpoint:records.create
Feature: Administrators manage roles and field access rules
  Roles such as Legal or CEO group people by what they are trusted with.
  Administrators create them, add people to them and write the rules that
  say which roles may see or change a field, all from the app itself.

  Background:
    Given Alice is a superuser
    And Bob can view and change customers
    And a customer "Acme" with email "legal@acme.test"

  Scenario: Adding a person to a role and a rule for it takes effect straight away
    When Alice adds Bob to the role "Legal"
    Then it succeeds
    When Alice adds a rule letting "Legal" edit the "email" of customers
    Then it succeeds
    When Bob changes the email of "Acme" to "deals@acme.test"
    Then it succeeds

  Scenario: A rule for everyone else needs no role
    When Alice adds a rule letting everyone else view the "email" of customers
    Then it succeeds
    When Bob changes the email of "Acme" to "bob@acme.test"
    Then it is rejected with "You may not change this field."

  Scenario: A rule must name a field the record type has
    When Alice adds a rule letting "Legal" edit the "special_terms" of customers
    Then it is rejected with "is not a field of customer"

  Scenario: A field has at most one rule per role
    Given people with the role "Legal" can view the email of customers
    When Alice adds a rule letting "Legal" edit the "email" of customers
    Then it is rejected with "This field already has a rule for this role."

  Scenario: A person holds a role only once
    Given Bob has the role "Legal"
    When Alice adds Bob to the role "Legal"
    Then it is rejected with "already has the role"

  Scenario Outline: Only people allowed to manage roles and rules may change them
    Given Carol can view customers
    When Carol <does>
    Then it is forbidden

    Examples:
      | does                                                       |
      | adds Bob to the role "Legal"                               |
      | adds a rule letting "Legal" edit the "email" of customers |
