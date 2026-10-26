@type:ASP @action:ASP.confirm
Feature: Confirm a proposal
  The assistant, MCP clients and background agents never change records
  themselves: they file proposals. When the person they work for confirms
  one, exactly what was proposed is applied, as a change of its own that can
  be undone.

  Background:
    Given Alice can view, add and change customers
    And a customer "Acme" with status "active"

  Scenario: Confirming a proposed edit applies it
    Given Alice proposed changing the name of "Acme" to "Acme Inc"
    When Alice confirms the proposal
    Then it succeeds
    And "Acme" has name "Acme Inc"
    And the proposal is confirmed by Alice

  Scenario: Confirming a proposed record creates it
    Given Alice proposed creating a customer "Globex"
    When Alice confirms the proposal
    Then it succeeds
    And the proposal created the customer "Globex"
    And the proposal is confirmed by Alice

  Scenario: Confirming a proposed action runs it
    Given Alice proposed running "Mark churned" on "Acme"
    When Alice confirms the proposal
    Then it succeeds
    And "Acme" has status "churned"

  Scenario: Confirming a proposed note adds it to the record
    Given Alice proposed adding the note "Called them about the renewal" to "Acme"
    When Alice confirms the proposal
    Then it succeeds
    And the note "Called them about the renewal" is added to "Acme"

  Scenario: Confirming a proposed undo reverts the earlier change
    Given Alice changed the status of "Acme" to "churned"
    And Alice proposed undoing that change
    When Alice confirms the proposal
    Then it succeeds
    And "Acme" has status "active"

  Scenario: The applied change is attributed to the person and the client that proposed it
    Given Alice's MCP client "Research Bot" proposed changing the name of "Acme" to "Acme Inc"
    When Alice confirms the proposal
    Then the change to "Acme" is recorded as made by Alice through the MCP client "Research Bot"

  Scenario: A confirmed proposal can be undone like any other change
    Given Alice proposed changing the name of "Acme" to "Acme Inc"
    And Alice confirmed the proposal
    When Alice undoes that change
    Then it succeeds
    And "Acme" has name "Acme"

  Scenario: A proposal that cannot be applied is marked as failed
    Given Alice proposed changing the status of "Acme" to "bogus"
    When Alice confirms the proposal
    Then it is rejected with "Validation failed"
    And the proposal failed with "Validation failed"
    And "Acme" still has status "active"

  Scenario: A proposed undo fails when the record was changed again since
    Given Bob can view and change customers
    And Alice changed the status of "Acme" to "churned"
    And Alice proposed undoing that change
    And Bob changed the status of "Acme" to "active"
    When Alice confirms the proposal
    Then it is rejected with "Not reverted: changed since"
    And the proposal failed with "Not reverted: changed since"

  Scenario: A proposal confirmed in two tabs at once is applied only once
    Given Alice proposed changing the name of "Acme" to "Acme Inc"
    When Alice confirms the proposal in two tabs at once
    Then it conflicts
    And "Acme" was changed only once
    And the proposal is confirmed by Alice

  Scenario: A proposal that was already confirmed cannot be confirmed again
    Given Alice proposed changing the name of "Acme" to "Acme Inc"
    And Alice confirmed the proposal
    When Alice confirms the proposal
    Then it is forbidden
    And "Acme" was changed only once

  Scenario: Confirming needs permission to make the change
    Given Carol can view customers
    And Carol proposed changing the name of "Acme" to "Acme Inc"
    When Carol confirms the proposal
    Then it is forbidden
    And the proposal is still pending
    And "Acme" still has name "Acme"

  Scenario: A proposal never does more than the person who filed it could
    Given Dave is a superuser
    And Carol can view customers
    And Carol proposed changing the name of "Acme" to "Acme Inc"
    When Dave confirms the proposal
    Then it is forbidden
    And the proposal is still pending

  Scenario: Confirming a proposed record needs permission to add records of that type
    Given Carol can view and change customers
    And Carol proposed creating a customer "Globex"
    When Carol confirms the proposal
    Then it is forbidden
    And no customer "Globex" exists

  Scenario: A proposal for a record that no longer exists cannot be confirmed
    Given Alice proposed changing the name of "Acme" to "Acme Inc"
    And "Acme" was permanently removed
    When Alice confirms the proposal
    Then it is forbidden
    And the proposal is still pending
