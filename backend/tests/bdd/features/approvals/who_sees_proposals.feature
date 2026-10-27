@type:ASP
Feature: Who sees and decides proposals
  Proposals are personal: each person sees and decides the ones filed on
  their behalf, and no-one else's. A proposal is fixed once filed, so what
  someone confirms is exactly what they read.

  Background:
    Given Alice can view and change customers
    And Bob can view and change customers
    And a customer "Acme"
    And Alice proposed changing the name of "Acme" to "Acme Inc"
    And Bob proposed changing the name of "Acme" to "Acme Ltd"

  Scenario: People see only their own proposals
    When Alice lists the proposals
    Then Alice sees only her own proposals

  Scenario: Superusers see every proposal
    Given Carol is a superuser
    When Carol lists the proposals
    Then Carol sees every proposal

  Scenario: Someone else's proposal cannot be confirmed
    When Alice confirms the proposal
    Then it is not found
    And the proposal is still pending

  Scenario: A proposal cannot be edited after it was filed
    When Bob changes the reasoning of "Bob's proposal" to "Acme asked for it."
    Then it is rejected with "A proposal can't be edited"

  Scenario: A proposal cannot be deleted by the person it was filed for
    When Bob deletes "Bob's proposal"
    Then it is forbidden
