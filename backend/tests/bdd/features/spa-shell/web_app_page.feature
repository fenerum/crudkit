@endpoint:crudkit_spa
Feature: The web app page
  Projects add CrudKit's web app at every address they do not use for
  something else, so any link into the app opens it. The page carries the
  project's app settings, and can be closed to people who are not signed in.

  Background:
    Given the web app is served at every other address

  Scenario: Any address opens the web app, even for someone not signed in
    When someone who is not signed in opens a page of the web app
    Then the web app is shown

  Scenario: A web app that requires signing in sends visitors to sign in first
    Given the web app requires signing in
    When someone who is not signed in opens a page of the web app
    Then they are sent to sign in first, coming back to that page afterwards

  Scenario: A web app that requires signing in opens for a signed-in person
    Given the web app requires signing in
    And Alice is a user without any permissions
    When Alice opens a page of the web app
    Then the web app is shown

  Scenario: Without settings the page is titled CrudKit and uses the default currency
    When someone who is not signed in opens a page of the web app
    Then the page title is "CrudKit"
    And the settings on the page include default_currency "DKK"
    And the settings on the page include the installed CrudKit version

  Scenario: The project's app settings are passed to the web app
    Given the web app is configured with:
      | app_name | Acme CRM |
    When someone who is not signed in opens a page of the web app
    Then the page title is "Acme CRM"
    And the settings on the page include app_name "Acme CRM"

  Scenario: App settings cannot break out of the page
    Given the web app is configured with:
      | note | </script><b> |
    When someone who is not signed in opens a page of the web app
    Then the settings on the page cannot break out of the page, yet still read "</script><b>" as note

  Scenario: The web app loads its files from where the project serves them
    Given static files are served from "/media-x/"
    When someone who is not signed in opens a page of the web app
    Then the web app loads its files from "/media-x/"
