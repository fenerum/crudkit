@command:backfill_ai_fields
Feature: Backfill AI fields
  When AI fields are added to a record type that already has records, or the
  AI was unavailable for a while, an operator fills in the gaps with the
  backfill_ai_fields command. It only picks records with an AI field still
  empty, and skips deleted ones.

  Background:
    Given Alice is a superuser
    And a topic "Hardware"
    And a ticket "Refund please"
    And a ticket "Printer broken"
    And a ticket "Old request"
    And the AI fields of "Printer broken" are already filled in, with the topic "Hardware"
    And Alice deleted "Old request"
    And the AI answers:
      | field   | value                        |
      | summary | The customer wants a refund. |

  Scenario: Records with empty AI fields are filled in straight away with --sync
    When an operator backfills AI fields with "--model testapp.Ticket --sync"
    Then the backfill reports "Found 1 instances with empty AI fields"
    And "Refund please" has summary "The customer wants a refund."
    And "Printer broken" still has summary "Already summarised."
    And the AI was asked about "Refund please" once

  Scenario: Without --sync the records are handed to the background worker
    Given the background worker only collects AI jobs
    When an operator backfills AI fields with "--model testapp.Ticket"
    Then the backfill reports "dispatched 1 tasks"
    And the background worker got AI jobs for "Refund please"
    And the AI was not asked

  Scenario Outline: The command refuses a model it cannot backfill
    When an operator backfills AI fields with "--model <model>"
    Then the backfill fails with "<message>"

    Examples:
      | model               | message                                       |
      | Ticket              | --model must be in app_label.ModelName format |
      | testapp.Nonexistent | Model testapp.Nonexistent not found           |
      | auth.User           | auth.User is not a BaseCrudKitModel           |
      | crudkit.Layout      | crudkit.Layout has no AI fields               |
