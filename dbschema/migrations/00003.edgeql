CREATE MIGRATION m1wq26blrkrphff5h6qgjbkncgzjqb22b44rz3eghtxcuqgnjkn2lq
    ONTO m1rrdvcfbi25ytprgzjwfkefuptphi4qynccehsdvgr7igg2gumr2a
{
  ALTER TYPE default::Guild {
      CREATE REQUIRED PROPERTY guild_id := (.discord_id);
  };
};
