@field:AISummaryField @field:AIBooleanField @field:AITagsField @field:AIForeignKeyField
Feature: AI fields are filled in by the AI
  Some fields are written by the AI rather than by people: a summary, a
  yes/no judgement, tags or a pick from related records. After a record is
  saved, a background job asks the AI to read the record and fills them in,
  keeping only answers that fit the field.

  Background:
    Given Alice can view and change tickets
    And a topic "Billing"
    And a topic "Technical"
    And a ticket "Refund please"

  Scenario: The AI fills in every kind of AI field
    Given the AI answers:
      | field     | value                           |
      | summary   | The customer wants a refund.    |
      | is urgent | yes                             |
      | tags      | billing and refund              |
      | topic     | Billing                         |
    When the AI fields of "Refund please" are filled in
    Then "Refund please" has summary "The customer wants a refund."
    And "Refund please" is urgent according to the AI
    And "Refund please" is tagged billing and refund
    And "Refund please" has topic "Billing"

  Scenario: Fields the AI does not answer keep their value
    Given the AI answers:
      | field     | value |
      | is urgent | no    |
    And the summary of "Refund please" is "Written earlier."
    When the AI fields of "Refund please" are filled in
    Then "Refund please" is not urgent according to the AI
    And "Refund please" still has summary "Written earlier."

  Scenario: Only the first ten tags are kept
    Given the AI answers:
      | field | value                                                                 |
      | tags  | one, two, three, four, five, six, seven, eight, nine, ten and eleven |
    When the AI fields of "Refund please" are filled in
    Then "Refund please" is tagged one, two, three, four, five, six, seven, eight, nine and ten

  Scenario: The AI picks a topic from the topics that are not deleted
    Given Alice can view and delete topics
    And a topic "Legacy"
    And Alice deleted "Legacy"
    And the AI answers:
      | field | value     |
      | topic | Technical |
    When the AI fields of "Refund please" are filled in
    Then the AI was offered the topics "Billing" and "Technical"
    And "Refund please" has topic "Technical"

  Scenario: A topic that no longer exists is not used
    Given a topic "Shipping"
    And the AI answers:
      | field   | value                     |
      | topic   | Shipping                  |
      | summary | The parcel never arrived. |
    And "Shipping" was permanently removed
    When the AI fields of "Refund please" are filled in
    Then "Refund please" has topic ""
    And "Refund please" has summary "The parcel never arrived."

  @known-bug
  Scenario: A topic answer that is not one of the topics leaves the topic empty
    Given the AI answers:
      | field   | value                        |
      | summary | The customer wants a refund. |
    And the AI answers the topic with the text "billing" instead of picking one
    When the AI fields of "Refund please" are filled in
    Then "Refund please" has topic ""
    And "Refund please" has summary "The customer wants a refund."

  Scenario: People cannot type into AI fields
    When Alice changes the summary of "Refund please" to "My own summary"
    Then "Refund please" has summary ""

  Scenario: Nothing is filled in while the AI service is unavailable
    Given the AI service is unavailable
    When the AI fields of "Refund please" are filled in
    Then the AI fields of "Refund please" are empty

  Scenario: Nothing is filled in when no AI model is configured
    Given no AI model is configured
    When the AI fields of "Refund please" are filled in
    Then the AI was not asked
    And the AI fields of "Refund please" are empty
