CREATE MIGRATION m1qnchirxfgnlqwf6hcpwrkwlvfzrzarkcaxk4mxm6khz3bgjxyfta
    ONTO initial
{
  CREATE ABSTRACT TYPE default::Snowflake {
      CREATE PROPERTY created_at -> std::datetime {
          SET readonly := true;
      };
      CREATE REQUIRED PROPERTY discord_id -> std::bigint {
          SET readonly := true;
          CREATE CONSTRAINT std::exclusive;
          CREATE CONSTRAINT std::min_value(0n);
      };
      CREATE INDEX ON (.discord_id);
  };
  CREATE ABSTRACT TYPE default::Channel EXTENDING default::Snowflake {
      CREATE REQUIRED PROPERTY channel_id := (.discord_id);
  };
  CREATE TYPE default::DMChannel EXTENDING default::Channel;
  CREATE SCALAR TYPE default::bounded_str EXTENDING std::str {
      CREATE CONSTRAINT std::max_len_value(300);
      CREATE CONSTRAINT std::min_len_value(1);
  };
  CREATE TYPE default::GroupChannel EXTENDING default::Channel {
      CREATE PROPERTY name -> default::bounded_str {
          CREATE CONSTRAINT std::min_len_value(0);
      };
  };
  CREATE TYPE default::GuildChannel EXTENDING default::Channel {
      CREATE PROPERTY name -> default::bounded_str {
          CREATE CONSTRAINT std::min_len_value(0);
      };
  };
  CREATE ABSTRACT TYPE default::Quote {
      CREATE REQUIRED PROPERTY keyword -> default::bounded_str;
      CREATE SINGLE LINK last_used_in -> default::Snowflake;
      CREATE REQUIRED PROPERTY created_at -> std::datetime {
          SET default := (std::datetime_current());
          SET readonly := true;
      };
      CREATE PROPERTY last_used_at -> std::datetime;
      CREATE REQUIRED PROPERTY quote_text -> std::str {
          CREATE CONSTRAINT std::max_len_value(1700);
          CREATE CONSTRAINT std::min_len_value(1);
      };
      CREATE REQUIRED PROPERTY times_used -> std::int32 {
          SET default := 0;
          CREATE CONSTRAINT std::min_value(0);
      };
  };
  CREATE TYPE default::ChannelQuote EXTENDING default::Quote {
      CREATE REQUIRED SINGLE LINK channel -> default::Channel {
          SET readonly := true;
      };
      CREATE INDEX ON (.channel);
      CREATE INDEX ON ((.channel, .keyword));
  };
  CREATE TYPE default::User EXTENDING default::Snowflake {
      CREATE REQUIRED PROPERTY user_id := (.discord_id);
      CREATE REQUIRED PROPERTY is_bot -> std::bool {
          SET default := false;
      };
      CREATE REQUIRED PROPERTY is_owner -> std::bool {
          SET default := false;
      };
      CREATE REQUIRED PROPERTY name -> default::bounded_str;
      CREATE REQUIRED PROPERTY tag -> default::bounded_str;
  };
  ALTER TYPE default::Quote {
      CREATE SINGLE LINK created_by -> default::User;
      CREATE SINGLE LINK last_used_by -> default::User;
  };
  ALTER TYPE default::DMChannel {
      CREATE REQUIRED SINGLE LINK user -> default::User {
          SET readonly := true;
      };
  };
  CREATE TYPE default::GlobalQuote EXTENDING default::Quote {
      ALTER PROPERTY keyword {
          SET OWNED;
          SET REQUIRED;
          SET TYPE default::bounded_str;
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE INDEX ON (.keyword);
  };
  ALTER TYPE default::GroupChannel {
      CREATE REQUIRED MULTI LINK users -> default::User;
  };
  CREATE TYPE default::Guild EXTENDING default::Snowflake {
      CREATE OPTIONAL SINGLE LINK log_channel -> default::GuildChannel;
      CREATE MULTI LINK users -> default::User;
      CREATE REQUIRED PROPERTY guild_id := (.discord_id);
      CREATE REQUIRED PROPERTY name -> default::bounded_str;
  };
  ALTER TYPE default::GuildChannel {
      CREATE REQUIRED SINGLE LINK guild -> default::Guild {
          SET readonly := true;
      };
  };
  ALTER TYPE default::Guild {
      CREATE MULTI LINK channels := (.<guild[IS default::GuildChannel]);
  };
  ALTER TYPE default::User {
      CREATE MULTI LINK guilds := (.<users[IS default::Guild]);
  };
  CREATE TYPE default::GuildQuote EXTENDING default::Quote {
      CREATE REQUIRED SINGLE LINK guild -> default::Guild {
          SET readonly := true;
      };
      CREATE INDEX ON ((.guild, .keyword));
      CREATE INDEX ON (.guild);
  };
};
