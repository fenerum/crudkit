@type:ASP @action:ASP.skip
Feature: Skip a proposal
  A person who does not want a proposed change skips it. Nothing is changed,
  and the decision is final: a skipped proposal cannot be confirmed later.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And Alice proposed changing the name of "Acme" to "Acme Inc"

  Scenario: Skipping a proposal changes nothing
    When Alice skips the proposal
    Then it succeeds
    And the proposal is skipped by Alice
    And "Acme" still has name "Acme"

  Scenario: A skipped proposal cannot be confirmed afterwards
    Given Alice skipped the proposal
    When Alice confirms the proposal
    Then it is forbidden
    And the proposal is skipped by Alice
    And "Acme" still has name "Acme"

  Scenario: A confirmed proposal cannot be skipped afterwards
    Given Alice confirmed the proposal
    When Alice skips the proposal
    Then it is forbidden
    And the proposal is confirmed by Alice
