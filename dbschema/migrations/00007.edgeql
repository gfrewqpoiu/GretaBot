CREATE MIGRATION m1ejqrtscyftpu5qxf53t6bg6wkhnio3hvfyujby46xu5paihxwbfq
    ONTO m1giluufkk7r3i2hzb3z3kkeel7z7taksq37fyoybgipk4v5vctnfa
{
  ALTER TYPE default::ChannelQuote {
      ALTER LINK channel {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
  ALTER TYPE default::DMChannel {
      ALTER LINK user {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
  ALTER TYPE default::Guild {
      ALTER LINK log_channel {
          ON TARGET DELETE  ALLOW;
      };
  };
  ALTER TYPE default::GuildChannel {
      ALTER LINK guild {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
  ALTER TYPE default::GuildQuote {
      ALTER LINK guild {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
};
