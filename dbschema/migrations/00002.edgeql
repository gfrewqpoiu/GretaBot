CREATE MIGRATION m1rrdvcfbi25ytprgzjwfkefuptphi4qynccehsdvgr7igg2gumr2a
    ONTO m1et436pty7dsfgf72vvrooff7ccmrgjcu3jycze735xuh5dzlo2ta
{
  ALTER TYPE default::Snowflake {
      ALTER PROPERTY created_at {
          SET readonly := true;
      };
  };
  ALTER TYPE default::DMChannel {
      ALTER LINK user {
          SET readonly := true;
      };
  };
  ALTER TYPE default::GuildChannel {
      ALTER LINK guild {
          SET readonly := true;
      };
  };
};
