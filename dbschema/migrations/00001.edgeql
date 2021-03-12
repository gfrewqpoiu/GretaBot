CREATE MIGRATION m1et436pty7dsfgf72vvrooff7ccmrgjcu3jycze735xuh5dzlo2ta
    ONTO initial
{
  CREATE ABSTRACT TYPE default::Snowflake {
      CREATE PROPERTY created_at -> std::datetime;
      CREATE REQUIRED PROPERTY discord_id -> std::bigint {
          SET readonly := true;
          CREATE CONSTRAINT std::exclusive;
          CREATE CONSTRAINT std::min_value(0n);
      };
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
      CREATE SINGLE LINK last_used_in -> default::Snowflake;
      CREATE REQUIRED PROPERTY created_at -> std::datetime {
          SET default := (std::datetime_current());
          SET readonly := true;
      };
      CREATE REQUIRED PROPERTY keyword -> default::bounded_str;
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
      CREATE REQUIRED PROPERTY channel_id := (.channel.discord_id);
  };
  CREATE TYPE default::User EXTENDING default::Snowflake {
      CREATE REQUIRED PROPERTY user_id := (.discord_id);
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
      CREATE REQUIRED SINGLE LINK user -> default::User;
  };
  CREATE TYPE default::GlobalQuote EXTENDING default::Quote {
      ALTER PROPERTY keyword {
          SET OWNED;
          SET REQUIRED;
          SET TYPE default::bounded_str;
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::GroupChannel {
      CREATE REQUIRED MULTI LINK users -> default::User;
  };
  CREATE TYPE default::Guild EXTENDING default::Snowflake {
      CREATE MULTI LINK channels -> default::GuildChannel;
      CREATE MULTI LINK users -> default::User;
      CREATE REQUIRED PROPERTY name -> default::bounded_str;
  };
  CREATE TYPE default::GuildQuote EXTENDING default::Quote {
      CREATE REQUIRED SINGLE LINK guild -> default::Guild {
          SET readonly := true;
      };
      CREATE REQUIRED PROPERTY guild_id := (.guild.discord_id);
  };
  ALTER TYPE default::GuildChannel {
      CREATE REQUIRED SINGLE LINK guild -> default::Guild;
  };
};
