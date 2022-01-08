CREATE MIGRATION m1bwzxcy6yjqwsvoe5c22ukbujtzjsp24sdmxek5tku6nndxm5gb5q
    ONTO m137hiusofqkybmnzg3ocra6raza3whni5tridthonc2wim7avpquq
{
  ALTER TYPE default::User {
      ALTER PROPERTY discriminator {
          SET REQUIRED USING (<default::discord_tag><std::str>(.full_tag)[-5:]);
      };
  };
};
