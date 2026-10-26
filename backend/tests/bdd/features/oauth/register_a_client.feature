@endpoint:crudkit_mcp_oauth_register
Feature: An MCP client registers itself
  AI tools such as Claude register themselves before asking a person for
  access, so nobody has to hand out client IDs. Registration only checks that
  the client says who it is and where people are sent back to after signing in.

  Scenario: A client with a name and a redirect address is registered
    When an MCP client registers as "My App" with a secure redirect address
    Then the client is registered as "My App"

  Scenario: A client must say what it is called
    When an MCP client registers without a name
    Then the registration is refused with "client_name is required"

  Scenario Outline: A client must give between one and ten redirect addresses, as text
    When an MCP client registers as "My App" with <addresses>
    Then the registration is refused with "<message>"

    Examples:
      | addresses                            | message                            |
      | no redirect addresses                | redirect_uris must be a non-empty list |
      | 11 redirect addresses                | Too many redirect_uris (max 10)    |
      | a redirect address that is not text  | Each redirect_uri must be a string |

  Scenario: Ten redirect addresses are allowed
    When an MCP client registers as "My App" with 10 redirect addresses
    Then the client is registered as "My App"

  Scenario: In production a redirect address must be secure
    Given the server runs in production mode
    When an MCP client registers as "My App" with an unencrypted redirect address on "app.example.com"
    Then the registration is refused with "redirect_uris must use HTTPS"

  Scenario Outline: In production a desktop app may still be sent back to the person's own computer
    Given the server runs in production mode
    When an MCP client registers as "CLI App" with an unencrypted redirect address on "<host>"
    Then the client is registered as "CLI App"

    Examples:
      | host      |
      | localhost |
      | 127.0.0.1 |
      | [::1]     |

  Scenario: In debug mode any redirect address is allowed
    Given the server runs in debug mode
    When an MCP client registers as "My App" with an unencrypted redirect address on "app.example.com"
    Then the client is registered as "My App"

  Scenario: Registering is throttled after 30 clients an hour from one address
    Given 30 MCP clients registered within the hour
    When an MCP client registers as "One Too Many" with a secure redirect address
    Then registering is throttled
