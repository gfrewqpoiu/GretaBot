CREATE MIGRATION m137hiusofqkybmnzg3ocra6raza3whni5tridthonc2wim7avpquq
    ONTO m1wqsygnsntchjly2jrw7exzos54p23x5qy5hgcw233r6wdjee3m5q
{
  ALTER TYPE default::User {
      CREATE PROPERTY discriminator -> default::discord_tag;
  };
};
